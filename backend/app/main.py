"""
شعر — Arabic Poetry Platform
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time

from app.core.config import settings
from app.core.database import create_tables
from app.core.cache import get_redis, close_redis
from app.core.exceptions import NotFoundException, PoetryException
from app.api.v1.router import api_router

# ── Logging ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting شعر Platform...")

    # Auto-create tables (safe — only creates missing ones)
    try:
        await create_tables()
    except Exception as e:
        logger.warning(f"⚠️ Table creation failed: {e}")

    # Initialize Meilisearch indices (skip if URL not configured)
    if settings.meilisearch_url:
        try:
            await _setup_meilisearch()
            logger.info("✅ Meilisearch ready")
        except Exception as e:
            logger.warning(f"⚠️ Meilisearch setup failed (non-critical): {e}")
    else:
        logger.info("ℹ️ Meilisearch not configured — search uses discovery only")

    # Test Redis
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}")

    logger.info("✅ Platform ready!")
    yield

    # Shutdown
    await close_redis()
    logger.info("👋 Platform shut down")


async def _setup_meilisearch():
    """Initialize Meilisearch indices with Arabic config."""
    from meilisearch_python_sdk import AsyncClient
    from app.search.meilisearch_config import (
        VERSES_INDEX_CONFIG, POETS_INDEX_CONFIG, POEMS_INDEX_CONFIG
    )

    async with AsyncClient(
        url=settings.meilisearch_url,
        api_key=settings.meilisearch_key,
    ) as client:
        # Create/update indices
        for index_name, config in [
            ("verses", VERSES_INDEX_CONFIG),
            ("poets", POETS_INDEX_CONFIG),
            ("poems", POEMS_INDEX_CONFIG),
        ]:
            try:
                index = client.index(index_name)
                # Update settings (idempotent)
                if "searchableAttributes" in config:
                    await index.update_searchable_attributes(config["searchableAttributes"])
                if "filterableAttributes" in config:
                    await index.update_filterable_attributes(config["filterableAttributes"])
                if "sortableAttributes" in config:
                    await index.update_sortable_attributes(config["sortableAttributes"])
                if "stopWords" in config:
                    await index.update_stop_words(config["stopWords"])
                if "synonyms" in config:
                    await index.update_synonyms(config["synonyms"])
                if "rankingRules" in config:
                    await index.update_ranking_rules(config["rankingRules"])
            except Exception as e:
                logger.debug(f"Index {index_name} setup: {e}")


# ── App Factory ───────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="شعر — Arabic Poetry Platform",
        description="Production-grade Arabic poetry search and discovery platform",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ──────────────────────
    @app.middleware("http")
    async def add_process_time(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        process_time = (time.time() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{process_time:.0f}"
        return response

    # ── Exception handlers ────────────────────────────
    @app.exception_handler(NotFoundException)
    async def not_found_handler(request: Request, exc: NotFoundException):
        return JSONResponse(
            status_code=404,
            content={"error": exc.code, "message": exc.message},
        )

    @app.exception_handler(PoetryException)
    async def poetry_exception_handler(request: Request, exc: PoetryException):
        return JSONResponse(
            status_code=400,
            content={"error": exc.code, "message": exc.message},
        )

    # ── Routers ───────────────────────────────────────
    app.include_router(api_router)

    # ── Health check ──────────────────────────────────
    @app.get("/health", tags=["system"])
    async def health():
        try:
            redis = await get_redis()
            redis_ok = await redis.ping()
        except Exception:
            redis_ok = False

        return {
            "status": "ok",
            "redis": redis_ok,
            "version": settings.app_version,
            "environment": settings.environment,
        }

    @app.get("/", tags=["system"])
    async def root():
        return {
            "name": "شعر Arabic Poetry Platform API",
            "version": settings.app_version,
            "docs": "/docs",
        }

    # ── Remote seed endpoint ─────────────────────────
    @app.post("/admin/seed", tags=["system"])
    async def seed_database(key: str = ""):
        if key != settings.secret_key:
            return {"error": "unauthorized"}

        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import text
        from app.models import Poet, Poem, Verse, Category, PoemCategory
        from app.utils.arabic_normalizer import normalizer
        import uuid

        engine = create_async_engine(settings.async_database_url)
        Session = async_sessionmaker(engine, expire_on_commit=False)

        async with engine.begin() as conn:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:
                pass

        from app.core.database import Base
        import app.models as _m
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        CATEGORIES = [
            {"name_ar": "الغزل والحب", "name_en": "Love", "slug": "love", "icon": "heart", "color": "#E74C3C", "display_order": 1},
            {"name_ar": "الحكمة", "name_en": "Wisdom", "slug": "wisdom", "icon": "moon", "color": "#8E44AD", "display_order": 2},
            {"name_ar": "الفخر", "name_en": "Pride", "slug": "pride", "icon": "sword", "color": "#E67E22", "display_order": 3},
            {"name_ar": "الرثاء", "name_en": "Elegy", "slug": "elegy", "icon": "dove", "color": "#95A5A6", "display_order": 4},
            {"name_ar": "الشوق والحنين", "name_en": "Longing", "slug": "longing", "icon": "wave", "color": "#3498DB", "display_order": 5},
            {"name_ar": "الوصف", "name_en": "Description", "slug": "description", "icon": "leaf", "color": "#27AE60", "display_order": 6},
            {"name_ar": "المدح", "name_en": "Praise", "slug": "praise", "icon": "crown", "color": "#F1C40F", "display_order": 7},
            {"name_ar": "الطبيعة", "name_en": "Nature", "slug": "nature", "icon": "flower", "color": "#1ABC9C", "display_order": 8},
        ]

        POETS = [
            {"name_ar": "أبو الطيب المتنبي", "name_en": "Al-Mutanabbi", "slug": "almutanabbi", "bio_ar": "أعظم شعراء العرب", "era": "abbasid", "birth_year": 915, "death_year": 965, "is_verified": True, "poem_count": 0, "verse_count": 0},
            {"name_ar": "امرؤ القيس", "name_en": "Imru al-Qays", "slug": "imrualqays", "bio_ar": "صاحب المعلقة الشهيرة", "era": "pre_islamic", "death_year": 540, "is_verified": True, "poem_count": 0, "verse_count": 0},
            {"name_ar": "محمود درويش", "name_en": "Mahmoud Darwish", "slug": "mahmouddarwish", "bio_ar": "شاعر المقاومة الفلسطينية", "era": "contemporary", "birth_year": 1941, "death_year": 2008, "is_verified": True, "poem_count": 0, "verse_count": 0},
            {"name_ar": "نزار قباني", "name_en": "Nizar Qabbani", "slug": "nizarqabbani", "bio_ar": "شاعر الحب والمرأة", "era": "contemporary", "birth_year": 1923, "death_year": 1998, "is_verified": True, "poem_count": 0, "verse_count": 0},
            {"name_ar": "أحمد شوقي", "name_en": "Ahmad Shawqi", "slug": "ahmadshawqi", "bio_ar": "أمير الشعراء", "era": "modern", "birth_year": 1868, "death_year": 1932, "is_verified": True, "poem_count": 0, "verse_count": 0},
            {"name_ar": "الخنساء", "name_en": "Al-Khansa", "slug": "alkhansa", "bio_ar": "أعظم شاعرات العرب", "era": "pre_islamic", "birth_year": 575, "death_year": 664, "is_verified": True, "poem_count": 0, "verse_count": 0},
        ]

        POEMS = [
            {"poet_slug": "almutanabbi", "title_ar": "على قدر أهل العزم", "slug": "almutanabbi-ala-qadri", "meter": "البسيط", "era": "abbasid", "categories": ["pride", "wisdom"], "verses": [
                ("عَلى قَدرِ أَهلِ العَزمِ تَأتي العَزائِمُ", "وَتَأتي عَلى قَدرِ الكِرامِ المَكارِمُ", True),
                ("وَتَعظُمُ في عَينِ الصَغيرِ صِغارُها", "وَتَصغُرُ في عَينِ العَظيمِ العَظائِمُ", True),
                ("يُكَلِّفُ سَيفُ الدَولَةِ الجَيشَ هَمَّهُ", "وَقَد عَجَزَت عَنهُ الجُيوشُ الخَضارِمُ", False),
            ]},
            {"poet_slug": "almutanabbi", "title_ar": "الخيل والليل والبيداء", "slug": "almutanabbi-alkhayl", "meter": "الطويل", "era": "abbasid", "categories": ["pride", "description"], "verses": [
                ("الخَيلُ وَاللَيلُ وَالبَيداءُ تَعرِفُني", "وَالسَيفُ وَالرُمحُ وَالقِرطاسُ وَالقَلَمُ", True),
                ("أَنا الَّذي نَظَرَ الأَعمى إِلى أَدَبي", "وَأَسمَعَت كَلِماتي مَن بِهِ صَمَمُ", True),
                ("أَنامُ مِلءَ جُفوني عَن شَوارِدِها", "وَيَسهَرُ الخَلقُ جَرّاها وَيَختَصِمُ", True),
            ]},
            {"poet_slug": "imrualqays", "title_ar": "معلقة امرئ القيس", "slug": "imrualqays-muallaqah", "meter": "الطويل", "era": "pre_islamic", "categories": ["love", "description"], "verses": [
                ("قِفا نَبكِ مِن ذِكرى حَبيبٍ وَمَنزِلِ", "بِسِقطِ اللِوى بَينَ الدَخولِ فَحَومَلِ", True),
                ("وَإِنَّ شِفائي عَبرَةٌ مُهَراقَةٌ", "فَهَل عِندَ رَسمٍ دارِسٍ مِن مُعَوَّلِ", True),
            ]},
            {"poet_slug": "mahmouddarwish", "title_ar": "على هذه الأرض", "slug": "darwish-ala-hathihi", "meter": "التفعيلة", "era": "contemporary", "categories": ["longing"], "verses": [
                ("على هذه الأرض ما يستحق الحياة", "", True),
                ("على هذه الأرض سيدة الأرض أم الابتداء", "", False),
            ]},
            {"poet_slug": "nizarqabbani", "title_ar": "قارئة الفنجان", "slug": "qabbani-qariate", "meter": "التفعيلة", "era": "contemporary", "categories": ["love"], "verses": [
                ("جلست والخوف بعينيها", "تتأمل فنجاني المقلوب", True),
                ("قالت يا ولدي لا تحزن", "فالحب عليك هو المكتوب", True),
            ]},
            {"poet_slug": "ahmadshawqi", "title_ar": "نهج البردة", "slug": "shawqi-nahj-alburdah", "meter": "البسيط", "era": "modern", "categories": ["praise"], "verses": [
                ("رِيمٌ عَلى القاعِ بَينَ البانِ وَالعَلَمِ", "أَحَلَّ سَفكَ دَمي في الأَشهُرِ الحُرُمِ", True),
                ("وَما نَيلُ المَطالِبِ بِالتَمَنّي", "وَلَكِن تُؤخَذُ الدُنيا غِلابا", True),
            ]},
            {"poet_slug": "alkhansa", "title_ar": "رثاء صخر", "slug": "alkhansa-rithaa-sakhr", "meter": "الوافر", "era": "pre_islamic", "categories": ["elegy"], "verses": [
                ("وَإِنَّ صَخراً لَتَأتَمُّ الهُداةُ بِهِ", "كَأَنَّهُ عَلَمٌ في رَأسِهِ نارُ", True),
                ("قَذى بِعَينِكِ أَم بِالعَينِ عُوّارُ", "أَم ذَرَفَت إِذ خَلَت مِن أَهلِها الدّارُ", True),
            ]},
        ]

        async with Session() as session:
            from sqlalchemy import select, func
            existing = (await session.execute(select(func.count()).select_from(Poet))).scalar()
            if existing and existing > 0:
                return {"message": f"Database already has {existing} poets, skipping seed"}

            cat_map = {}
            for cd in CATEGORIES:
                cat = Category(**cd)
                session.add(cat)
                await session.flush()
                cat_map[cd["slug"]] = cat

            poet_map = {}
            for pd in POETS:
                poet = Poet(**pd)
                session.add(poet)
                await session.flush()
                poet_map[pd["slug"]] = poet

            total_verses = 0
            for pmd in POEMS:
                poet = poet_map[pmd["poet_slug"]]
                full_text = "\n".join(f"{h1} *** {h2}" if h2 else h1 for h1, h2, _ in pmd["verses"])
                poem = Poem(poet_id=poet.id, title_ar=pmd["title_ar"], slug=pmd["slug"], full_text=full_text, meter=pmd.get("meter"), verse_count=len(pmd["verses"]), era=pmd.get("era"), is_verified=True, is_published=True)
                session.add(poem)
                await session.flush()

                for cs in pmd.get("categories", []):
                    if cs in cat_map:
                        session.add(PoemCategory(poem_id=poem.id, category_id=cat_map[cs].id))

                for i, (h1, h2, famous) in enumerate(pmd["verses"], 1):
                    fv = f"{h1} *** {h2}" if h2 else h1
                    session.add(Verse(poem_id=poem.id, poet_id=poet.id, position=i, hemistich_1=h1, hemistich_2=h2 or None, full_verse=fv, full_verse_normalized=normalizer.normalize(fv), hemistich_1_normalized=normalizer.normalize(h1), hemistich_2_normalized=normalizer.normalize(h2) if h2 else None, poet_name_ar=poet.name_ar, poet_slug=poet.slug, poem_title_ar=pmd["title_ar"], poem_slug=pmd["slug"], is_famous=famous))
                    total_verses += 1

                poet.poem_count += 1
                poet.verse_count += len(pmd["verses"])

            await session.commit()

        return {"message": f"Seeded {len(POETS)} poets, {len(POEMS)} poems, {total_verses} verses, {len(CATEGORIES)} categories"}

    # ── Ashaar dataset import (batch mode) ───────────
    app.state.ashaar_cache = None  # holds fetched poems between batch calls
    app.state.ashaar_offset = 0
    app.state.import_totals = {"poets": 0, "poems": 0, "verses": 0}

    @app.post("/admin/import-ashaar", tags=["system"])
    async def import_ashaar(key: str = "", batch_size: int = 200):
        if key != settings.secret_key:
            return {"error": "unauthorized"}

        import re
        import httpx
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy import select
        from app.models import Poet, Poem, Verse
        from app.utils.arabic_normalizer import normalizer

        ERA_MAP = {
            "العصر الجاهلي": "pre_islamic", "الجاهلي": "pre_islamic",
            "صدر الإسلام": "islamic_early", "عصر صدر الإسلام": "islamic_early",
            "العصر الأموي": "umayyad", "الأموي": "umayyad",
            "العصر العباسي": "abbasid", "العباسي": "abbasid",
            "العصر الأندلسي": "andalusian",
            "العصر المملوكي": "mamluk", "العصر الأيوبي": "abbasid",
            "العصر العثماني": "ottoman",
            "العصر الحديث": "modern", "الحديث": "modern",
            "العصر المعاصر": "contemporary", "المعاصر": "contemporary",
        }
        METER_NAMES = ["البسيط", "الخفيف", "الرجز", "الرمل", "السريع", "الطويل", "الكامل", "المتدارك", "المتقارب", "المجتث", "المديد", "المقتضب", "المنسرح", "المواليا", "الهزج", "الوافر", "عامي"]

        def map_era(s):
            for ar, slug in ERA_MAP.items():
                if ar in (s or ""):
                    return slug
            return "abbasid"

        def make_slug(text):
            try:
                from unidecode import unidecode
                return re.sub(r"[^a-z0-9]+", "-", unidecode(text).lower()).strip("-")[:200] or "unknown"
            except Exception:
                return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:200] or "unknown"

        def parse_verses(text):
            verses = []
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = None
                for sep in ["***", "\t", "   "]:
                    if sep in line:
                        parts = [p.strip() for p in line.split(sep, 1) if p.strip()]
                        break
                h1, h2 = (parts[0], parts[1]) if parts and len(parts) == 2 else (line, "")
                if len(h1) > 2:
                    verses.append((h1, h2))
            return verses[:80]

        try:
            # Fetch batch from HuggingFace rows API
            hf_offset = app.state.ashaar_offset
            poems_data = []

            async with httpx.AsyncClient(timeout=60.0) as client:
                fetched = 0
                while fetched < batch_size:
                    url = f"https://datasets-server.huggingface.co/rows?dataset=arbml%2FAshaar_dataset&config=default&split=train&offset={hf_offset}&length=100"
                    r = await client.get(url)
                    if r.status_code != 200:
                        break
                    rows = r.json().get("rows", [])
                    if not rows:
                        break

                    for item in rows:
                        row = item.get("row", {})
                        poet_name = (row.get("poet_name") or "").strip()
                        title = (row.get("poem_title") or "").strip()
                        verses_list = row.get("poem_verses") or []
                        text = row.get("text") or ""
                        raw_meter = row.get("poem_meter")
                        era = (row.get("poet_era") or "").strip()

                        if isinstance(raw_meter, int) and 0 <= raw_meter < len(METER_NAMES):
                            meter = METER_NAMES[raw_meter]
                        elif isinstance(raw_meter, str) and raw_meter not in ("", "nan"):
                            meter = str(raw_meter)
                        else:
                            meter = None

                        if not poet_name:
                            continue
                        if verses_list and isinstance(verses_list, list):
                            text = "\n".join(str(v) for v in verses_list if v)
                        if not text or len(text) < 10:
                            continue
                        if not title:
                            title = text.split("\n")[0][:60] or "قصيدة"

                        poems_data.append({"poet_name": poet_name, "title": title, "text": text, "meter": meter, "era": era})

                    hf_offset += 100
                    fetched += 100

            app.state.ashaar_offset = hf_offset

            if not poems_data:
                return {"status": "done", "message": "No more data to import", **app.state.import_totals, "hf_offset": hf_offset}

            # Import batch to DB
            engine = create_async_engine(settings.async_database_url, echo=False)
            Session = async_sessionmaker(engine, expire_on_commit=False)

            added_poets = 0
            added_poems = 0
            added_verses = 0

            async with Session() as session:
                existing_poem_slugs = set(r[0] for r in (await session.execute(select(Poem.slug))).fetchall())

                for pd in poems_data:
                    poet_slug = make_slug(pd["poet_name"])
                    poem_slug = f"{poet_slug}-{make_slug(pd['title'])}"[:580]
                    if poem_slug in existing_poem_slugs:
                        continue

                    # Get or create poet
                    poet = (await session.execute(select(Poet).where(Poet.slug == poet_slug))).scalar_one_or_none()
                    if not poet:
                        poet = Poet(name_ar=pd["poet_name"], slug=poet_slug, bio_ar="شاعر عربي", era=map_era(pd["era"]), nationality_ar="عربي", is_verified=True, poem_count=0, verse_count=0)
                        session.add(poet)
                        await session.flush()
                        added_poets += 1

                    verses = parse_verses(pd["text"])
                    if not verses:
                        continue

                    full_text = "\n".join(f"{h1} *** {h2}" if h2 else h1 for h1, h2 in verses)
                    poem = Poem(poet_id=poet.id, title_ar=pd["title"], slug=poem_slug, full_text=full_text, meter=pd["meter"], verse_count=len(verses), era=map_era(pd.get("era", "")), is_verified=True, is_published=True, source="ashaar/ARBML")
                    session.add(poem)
                    await session.flush()
                    existing_poem_slugs.add(poem_slug)

                    for pos, (h1, h2) in enumerate(verses, 1):
                        fv = f"{h1} *** {h2}" if h2 else h1
                        session.add(Verse(poem_id=poem.id, poet_id=poet.id, position=pos, hemistich_1=h1, hemistich_2=h2 or None, full_verse=fv, full_verse_normalized=normalizer.normalize(fv), hemistich_1_normalized=normalizer.normalize(h1), hemistich_2_normalized=normalizer.normalize(h2) if h2 else None, poet_name_ar=pd["poet_name"], poet_slug=poet_slug, poem_title_ar=pd["title"], poem_slug=poem_slug, is_famous=False))
                        added_verses += 1

                    added_poems += 1
                    poet.poem_count = (poet.poem_count or 0) + 1
                    poet.verse_count = (poet.verse_count or 0) + len(verses)

                await session.commit()

            t = app.state.import_totals
            t["poets"] += added_poets
            t["poems"] += added_poems
            t["verses"] += added_verses

            return {"status": "batch_done", "batch_added": {"poets": added_poets, "poems": added_poems, "verses": added_verses}, "totals": t, "hf_offset": hf_offset, "message": f"Call again to import next batch (offset={hf_offset})"}

        except Exception as e:
            logger.error(f"Ashaar import batch failed: {e}")
            return {"status": "error", "error": str(e), "hf_offset": app.state.ashaar_offset, "totals": app.state.import_totals}

    @app.get("/admin/import-status", tags=["system"])
    async def import_status():
        return {**app.state.import_totals, "hf_offset": app.state.ashaar_offset}

    return app


app = create_app()
