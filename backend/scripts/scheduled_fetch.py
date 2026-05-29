"""
Scheduled data fetcher — run daily/weekly to discover new poems from qafiyah.com.

Usage:
  python scripts/scheduled_fetch.py              # fetch + import + reindex
  python scripts/scheduled_fetch.py --fetch-only # fetch only (no DB import)

Deploy as:
  - Railway cron job: `python scripts/scheduled_fetch.py` on schedule "0 3 * * *" (daily 3 AM)
  - Windows Task Scheduler
  - GitHub Actions scheduled workflow
"""

import asyncio
import sys
import os
import json
import re
import time
import random
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE = "https://api.qafiyah.com"
STATE_FILE = os.path.join(os.path.dirname(__file__), "fetch_state.json")

SEARCH_TERMS = [
    "الحب", "الموت", "الحكمة", "الشوق", "الفراق", "الليل", "الصبح",
    "القلب", "السيف", "الخيل", "الدهر", "الزمان", "الأيام", "الدنيا",
    "البحر", "الشمس", "القمر", "الفجر", "المطر", "الجبل", "الروض",
    "العشق", "الهوى", "الحنين", "الغربة", "الوطن", "الحرب", "الفخر",
    "الرثاء", "المدح", "الهجاء", "الزهد", "التصوف", "الطبيعة",
    "ابن", "أبو", "محمد", "أحمد", "علي", "عبد", "عمر", "خالد",
    "المتنبي", "البحتري", "أبو تمام", "الخنساء", "الشنفرى",
    "بغداد", "دمشق", "الأندلس", "قرطبة", "غرناطة",
    "الطويل", "الكامل", "البسيط", "الوافر", "الرجز",
]


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"known_poem_slugs": [], "last_run": None, "total_fetched": 0}


def save_state(state: dict):
    state["last_run"] = datetime.utcnow().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


async def fetch_new_poems() -> list[dict]:
    state = load_state()
    known = set(state.get("known_poem_slugs", []))
    logger.info(f"Known poems: {len(known)}, starting discovery...")

    new_poems = []
    terms = random.sample(SEARCH_TERMS, min(20, len(SEARCH_TERMS)))

    limits = httpx.Limits(max_connections=3, max_keepalive_connections=2)
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-updater/1.0)"},
        limits=limits,
    ) as client:
        for i, term in enumerate(terms, 1):
            for page in range(1, 6):
                try:
                    r = await client.get(
                        f"{BASE}/search",
                        params={"q": term, "search_type": "poems", "match_type": "any", "page": page},
                        timeout=20,
                    )
                    if r.status_code != 200:
                        break
                    data = r.json()["data"]
                    results = data.get("results", [])
                    if not results:
                        break

                    for poem in results:
                        slug = poem.get("poem_slug", "")
                        if slug and slug not in known:
                            known.add(slug)
                            new_poems.append(poem)

                    if not data["pagination"]["hasNextPage"]:
                        break
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"Error fetching {term} p{page}: {e}")
                    break

            logger.info(f"[{i}/{len(terms)}] {term}: {len(new_poems)} new poems so far")
            await asyncio.sleep(0.5)

    state["known_poem_slugs"] = list(known)
    state["total_fetched"] = state.get("total_fetched", 0) + len(new_poems)
    save_state(state)

    logger.info(f"Discovered {len(new_poems)} new poems")
    return new_poems


async def import_poems(new_poems: list[dict]):
    if not new_poems:
        logger.info("No new poems to import")
        return

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select, text
    from app.core.config import settings
    from app.core.database import Base
    from app.models import Poet, Poem, Verse, Category, PoemCategory
    from app.utils.arabic_normalizer import normalizer
    import app.models  # noqa

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    ERA_MAP = {
        "جاهلي": "pre_islamic", "مخضرم": "islamic", "إسلامي": "islamic",
        "أموي": "umayyad", "عباسي": "abbasid", "أندلسي": "andalusian",
        "أيوبي": "abbasid", "مملوكي": "abbasid", "عثماني": "modern", "متأخر": "modern",
    }

    def map_era(era_ar: str) -> str:
        for ar, slug in ERA_MAP.items():
            if ar in era_ar:
                return slug
        return "abbasid"

    def parse_snippet(snippet: str) -> list[tuple[str, str]]:
        if not snippet:
            return []
        clean = re.sub(r"</?mark>", "", snippet)
        parts = [p.strip() for p in clean.split("*") if p.strip()]
        verses = []
        i = 0
        while i < len(parts):
            h1 = parts[i]
            h2 = parts[i + 1] if i + 1 < len(parts) else ""
            if len(h1) > 3:
                verses.append((h1, h2))
            i += 2
        if not verses:
            verses = [(p, "") for p in parts if len(p) > 3]
        return verses[:12]

    def make_slug(text: str) -> str:
        try:
            from unidecode import unidecode
            slug = re.sub(r"[^a-z0-9]+", "-", unidecode(text).lower()).strip("-")
        except ImportError:
            slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
        return slug[:200] or "poem"

    async with Session() as session:
        cat_rows = (await session.execute(select(Category))).scalars().all()
        cat_map = {c.slug: c for c in cat_rows}

        added_poets = 0
        added_poems = 0
        added_verses = 0

        for poem_raw in new_poems:
            poet_slug = poem_raw.get("poet_slug", "")
            poet_name = poem_raw.get("poet_name", "")
            title = poem_raw.get("poem_title", "")
            snippet = poem_raw.get("poem_snippet", "")
            era_ar = poem_raw.get("poet_era", "")

            if not poet_slug or not title or not snippet:
                continue

            verses = parse_snippet(snippet)
            if not verses:
                continue

            # Get or create poet
            existing_poet = (await session.execute(
                select(Poet).where(Poet.slug == poet_slug)
            )).scalar_one_or_none()

            if not existing_poet:
                poet = Poet(
                    name_ar=poet_name,
                    slug=poet_slug,
                    bio_ar=f"شاعر عربي من {era_ar}" if era_ar else "شاعر عربي",
                    era=map_era(era_ar),
                    nationality_ar="عربي",
                    is_verified=True,
                )
                session.add(poet)
                await session.flush()
                added_poets += 1
            else:
                poet = existing_poet

            # Check if poem already exists
            poem_slug = f"{poet_slug}-{make_slug(title)}"[:580]
            existing_poem = (await session.execute(
                select(Poem.id).where(Poem.slug == poem_slug)
            )).scalar_one_or_none()
            if existing_poem:
                continue

            full_text = "\n".join(f"{h1} *** {h2}" if h2 else h1 for h1, h2 in verses)
            meter = poem_raw.get("poem_meter", "") or None

            poem = Poem(
                poet_id=poet.id,
                title_ar=title,
                slug=poem_slug,
                full_text=full_text,
                meter=meter,
                verse_count=len(verses),
                era=map_era(era_ar),
                is_verified=True,
                is_published=True,
                source="qafiyah.com",
            )
            session.add(poem)
            await session.flush()

            # Assign default category
            default_cats = ["wisdom", "praise"] if "عباسي" in era_ar else ["wisdom"]
            for cs in default_cats:
                if cs in cat_map:
                    session.add(PoemCategory(poem_id=poem.id, category_id=cat_map[cs].id))

            for pos, (h1, h2) in enumerate(verses, 1):
                full_verse = f"{h1} *** {h2}" if h2 else h1
                session.add(Verse(
                    poem_id=poem.id,
                    poet_id=poet.id,
                    position=pos,
                    hemistich_1=h1,
                    hemistich_2=h2 or None,
                    full_verse=full_verse,
                    full_verse_normalized=normalizer.normalize(full_verse),
                    hemistich_1_normalized=normalizer.normalize(h1),
                    hemistich_2_normalized=normalizer.normalize(h2) if h2 else None,
                    poet_name_ar=poet_name,
                    poet_slug=poet_slug,
                    poem_title_ar=title,
                    poem_slug=poem_slug,
                    is_famous=False,
                ))
                added_verses += 1

            added_poems += 1
            poet.poem_count = (poet.poem_count or 0) + 1
            poet.verse_count = (poet.verse_count or 0) + len(verses)

            if added_poems % 50 == 0:
                await session.commit()
                logger.info(f"  Checkpoint: {added_poems} poems, {added_verses} verses")

        await session.commit()
        logger.info(f"Imported: {added_poets} new poets, {added_poems} poems, {added_verses} verses")

    # Reindex Meilisearch
    try:
        from meilisearch_python_sdk import AsyncClient
        logger.info("Re-indexing Meilisearch...")

        async with Session() as session:
            async with AsyncClient(url=settings.meilisearch_url, api_key=settings.meilisearch_key) as client:
                vi = client.index("verses")
                offset = 0
                while True:
                    rows = (await session.execute(
                        select(Verse).offset(offset).limit(500)
                    )).scalars().all()
                    if not rows:
                        break
                    docs = [{
                        "id": str(v.id), "full_verse": v.full_verse,
                        "full_verse_normalized": v.full_verse_normalized or v.full_verse,
                        "hemistich_1": v.hemistich_1, "hemistich_2": v.hemistich_2 or "",
                        "hemistich_1_normalized": v.hemistich_1_normalized or v.hemistich_1,
                        "hemistich_2_normalized": v.hemistich_2_normalized or "",
                        "poet_name_ar": v.poet_name_ar or "", "poet_slug": v.poet_slug or "",
                        "poem_title_ar": v.poem_title_ar or "", "poem_slug": v.poem_slug or "",
                        "poet_id": str(v.poet_id), "poem_id": str(v.poem_id),
                        "is_famous": v.is_famous, "view_count": v.view_count,
                    } for v in rows]
                    await vi.add_documents(docs, primary_key="id")
                    offset += 500
                logger.info(f"Meilisearch reindexed ({offset} verses)")
    except Exception as e:
        logger.warning(f"Meilisearch reindex failed: {e}")


async def main():
    t0 = time.time()
    fetch_only = "--fetch-only" in sys.argv

    new_poems = await fetch_new_poems()

    if not fetch_only:
        await import_poems(new_poems)

    elapsed = time.time() - t0
    logger.info(f"Done in {elapsed:.0f}s — {len(new_poems)} new poems")


if __name__ == "__main__":
    asyncio.run(main())
