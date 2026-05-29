"""
Qafiyah data harvester + importer.

Phase 1: Fetch all poets + poem snippets from api.qafiyah.com
Phase 2: Import into our poetry_db

Run: python -X utf8 scripts/fetch_qafiyah.py

The search API returns poem_snippet which contains real Arabic verse text
separated by '*'. Each snippet has ~6-10 verses per poem.
"""

import asyncio
import sys
import os
import json
import re
import time
import httpx
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)

BASE = "https://api.qafiyah.com"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "qafiyah_cache.json")

# ── Era mapping: qafiyah Arabic name → our era slug ──────────────────────────

ERA_MAP = {
    "جاهلي":   "pre_islamic",
    "مخضرم":   "islamic",
    "إسلامي":  "islamic",
    "أموي":    "umayyad",
    "عباسي":   "abbasid",
    "أندلسي":  "andalusian",
    "أيوبي":   "abbasid",        # Ayyubid → Abbasid era
    "مملوكي":  "abbasid",        # Mamluk → Abbasid (late)
    "عثماني":  "modern",         # Ottoman → Modern
    "متأخر":   "modern",         # Late → Modern
}

# ── Meter mapping ─────────────────────────────────────────────────────────────

METER_MAP = {
    "الطويل":    "الطويل",
    "الكامل":    "الكامل",
    "البسيط":    "البسيط",
    "الوافر":    "الوافر",
    "الرجز":     "الرجز",
    "الخفيف":    "الخفيف",
    "الرمل":     "الرمل",
    "السريع":    "السريع",
    "المتقارب":  "المتقارب",
    "المتدارك":  "المتدارك",
    "المجتث":    "المجتث",
    "المديد":    "المديد",
    "المنسرح":   "المنسرح",
    "الهزج":     "الهزج",
    "الجوانب":   "الجوانب",
    "المقتضب":   "المقتضب",
}

# ── Category mapping: meter/era → our category slugs ─────────────────────────

THEME_TO_CAT = {
    "غزل":     "love",
    "مدح":     "praise",
    "رثاء":    "elegy",
    "هجاء":    "satire",
    "فخر":     "pride",
    "وصف":     "description",
    "حكمة":    "wisdom",
    "زهد":     "zuhd",
    "اعتذار":  "apology",
    "ديني":    "religious",
    "وطني":    "patriotic",
    "حرب":     "war",
    "عتاب":    "lament",
    "شكوى":    "lament",
    "تصوف":    "sufi",
    "طبيعة":   "nature",
    "حنين":    "longing",
    "رحلة":    "travel",
}


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: Fetch data from API
# ─────────────────────────────────────────────────────────────────────────────

SEARCH_TERMS = [
    # Patronymics / kunya — cover most classical poets
    "ابن", "أبو", "بن", "ابنة", "أبي",
    # Common first names
    "محمد", "أحمد", "علي", "عبد", "يوسف", "إبراهيم",
    "عمر", "حسن", "الحسين", "الحسن", "يزيد", "مروان",
    "زيد", "سعد", "خالد", "عثمان", "سليمان", "عيسى",
    "هارون", "إسحاق", "الوليد", "هشام", "عبدالله",
    # Geographic/tribal nisbas
    "الكوفي", "البصري", "البغدادي", "الأندلسي",
    "المصري", "الشامي", "العراقي", "الحجازي",
    "التميمي", "القيسي", "العبسي", "الطائي",
    # Laqabs / epithets
    "الشاعر", "الأديب", "الفارس", "الملك",
]

POEM_TERMS = [
    # Common words in poem titles/content
    "قفا", "الخيل", "الليل", "الحب", "النفس",
    "الدهر", "الموت", "العيش", "السيف", "القلب",
    "الشمس", "القمر", "البدر", "الروض", "الماء",
    "الوطن", "الشعر", "الزمان", "الأيام", "الدنيا",
    "يا ليل", "أغار", "حبيبي", "عيني", "قلبي",
    "صبرا", "رثاء", "مدح", "غزل", "وصف",
]


async def search_poets(client: httpx.AsyncClient, query: str) -> list[dict]:
    """Fetch all pages of poet search results for a query."""
    poets = []
    page = 1
    while True:
        try:
            r = await client.get(
                f"{BASE}/search",
                params={"q": query, "search_type": "poets", "match_type": "any", "page": page},
                timeout=20,
            )
            if r.status_code != 200:
                break
            data = r.json()["data"]
            results = data.get("results", [])
            if not results:
                break
            poets.extend(results)
            if not data["pagination"]["hasNextPage"]:
                break
            page += 1
            await asyncio.sleep(0.3)  # be polite
        except Exception as e:
            print(f"  search_poets error ({query} p{page}): {e}")
            break
    return poets


async def search_poems_for_poet(client: httpx.AsyncClient, poet_name: str) -> list[dict]:
    """Search poems for a specific poet by name."""
    poems = []
    # Use first 2 significant words of the poet name for the query
    words = [w for w in poet_name.split() if len(w) > 1 and w not in ("بن", "أبو", "ابن", "أبي")]
    query = " ".join(words[:2]) if words else poet_name[:10]
    if len(query) < 2:
        query = poet_name[:10]

    page = 1
    while True:
        try:
            r = await client.get(
                f"{BASE}/search",
                params={
                    "q": query,
                    "search_type": "poems",
                    "match_type": "any",
                    "page": page,
                },
                timeout=20,
            )
            if r.status_code != 200:
                break
            data = r.json()["data"]
            results = data.get("results", [])
            # Filter to only this poet's poems
            poet_poems = [p for p in results if p.get("poet_slug") == ""]
            # Use all results if poet-filtering yields nothing
            if not poet_poems:
                poet_poems = [p for p in results]
            poems.extend(poet_poems)
            if not data["pagination"]["hasNextPage"] or page >= 5:
                break
            page += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"  search_poems error ({poet_name[:20]}): {e}")
            break
    return poems


async def search_poems_by_slug(client: httpx.AsyncClient, poet_slug: str, poet_name: str) -> list[dict]:
    """More targeted: search poems and filter by poet_slug."""
    all_poems = []
    # Try multiple search queries
    queries = []
    words = poet_name.split()
    if len(words) >= 2:
        queries.append(" ".join(words[-2:]))  # last 2 words (often the distinguishing name)
    queries.append(poet_slug.replace("-", " ")[:20])

    seen_slugs = set()
    for query in queries:
        if len(query) < 2:
            continue
        page = 1
        while page <= 3:
            try:
                r = await client.get(
                    f"{BASE}/search",
                    params={"q": query, "search_type": "poems", "match_type": "any", "page": page},
                    timeout=20,
                )
                if r.status_code != 200:
                    break
                data = r.json()["data"]
                results = data.get("results", [])
                for poem in results:
                    if poem.get("poet_slug") == poet_slug and poem["poem_slug"] not in seen_slugs:
                        seen_slugs.add(poem["poem_slug"])
                        all_poems.append(poem)
                if not data["pagination"]["hasNextPage"]:
                    break
                page += 1
                await asyncio.sleep(0.2)
            except Exception:
                break

    return all_poems


def parse_snippet(snippet: str) -> list[tuple[str, str]]:
    """
    Parse a poem snippet into (hemistich_1, hemistich_2) pairs.
    Snippet format: verse1*verse2*... with <mark> tags and * separators.
    Each '*' separated item may be a full verse or a hemistich.
    """
    if not snippet:
        return []

    # Remove HTML mark tags
    clean = re.sub(r"</?mark>", "", snippet)
    # Split on * separator
    parts = [p.strip() for p in clean.split("*") if p.strip()]

    verses = []
    i = 0
    while i < len(parts):
        h1 = parts[i]
        h2 = parts[i + 1] if i + 1 < len(parts) else ""
        # Skip very short entries (artifacts)
        if len(h1) > 3:
            verses.append((h1, h2))
        i += 2  # consume 2 parts per verse

    # If no pairs formed, treat each part as a standalone verse
    if not verses:
        verses = [(p, "") for p in parts if len(p) > 3]

    return verses[:12]  # max 12 verses per snippet


async def fetch_all_data() -> dict:
    """Fetch all poets and their poems from the API."""
    print("\n🌐 Phase 1: Fetching data from api.qafiyah.com...")

    all_poets: dict[str, dict] = {}   # slug → poet dict
    poet_poems: dict[str, list] = {}  # slug → list of poem dicts

    limits = httpx.Limits(max_connections=5, max_keepalive_connections=3)
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-importer/1.0)"},
        limits=limits,
    ) as client:

        # ── Step 1: Collect all poet slugs ────────────────────────────────────
        print("  Collecting poet slugs...")
        for term in SEARCH_TERMS:
            results = await search_poets(client, term)
            for p in results:
                slug = p.get("poet_slug", "")
                if slug and slug not in all_poets:
                    all_poets[slug] = {
                        "name_ar": p.get("poet_name", ""),
                        "slug": slug,
                        "era_ar": p.get("poet_era", ""),
                        "bio_ar": p.get("poet_bio", ""),
                    }
            await asyncio.sleep(0.5)

        print(f"  Found {len(all_poets)} unique poets")

        # ── Step 2: For each poet, find their poems ──────────────────────────
        print(f"  Fetching poems for {len(all_poets)} poets...")
        poet_slugs = list(all_poets.keys())

        for i, slug in enumerate(poet_slugs, 1):
            poet = all_poets[slug]
            name = poet["name_ar"]
            print(f"  [{i:>3}/{len(poet_slugs)}] {name[:30]:<30}", end="\r", flush=True)

            poems = await search_poems_by_slug(client, slug, name)
            if not poems:
                # Fallback: use broad poem search
                poems = await search_poems_for_poet(client, name)
                # Filter to this poet only
                poems = [p for p in poems if p.get("poet_slug") == slug]

            poet_poems[slug] = poems
            await asyncio.sleep(0.4)

        # ── Step 3: Also collect poems via broad poem search terms ────────────
        print("\n  Collecting additional poems via broad search...")
        seen_poem_slugs: set[str] = set()
        extra_poems: list[dict] = []

        for term in POEM_TERMS:
            try:
                r = await client.get(
                    f"{BASE}/search",
                    params={"q": term, "search_type": "poems", "match_type": "any", "page": 1},
                    timeout=20,
                )
                if r.status_code == 200:
                    results = r.json()["data"].get("results", [])
                    for p in results:
                        ps = p.get("poem_slug", "")
                        poet_s = p.get("poet_slug", "")
                        if ps and ps not in seen_poem_slugs:
                            seen_poem_slugs.add(ps)
                            extra_poems.append(p)
                            # Register poet if new
                            if poet_s and poet_s not in all_poets:
                                all_poets[poet_s] = {
                                    "name_ar": p.get("poet_name", ""),
                                    "slug": poet_s,
                                    "era_ar": p.get("poet_era", ""),
                                    "bio_ar": "",
                                }
                await asyncio.sleep(0.3)
            except Exception:
                pass

        # Merge extra_poems into poet_poems
        for p in extra_poems:
            slug = p.get("poet_slug", "")
            if slug:
                if slug not in poet_poems:
                    poet_poems[slug] = []
                if not any(x["poem_slug"] == p["poem_slug"] for x in poet_poems[slug]):
                    poet_poems[slug].append(p)

    print(f"\n  Total unique poets: {len(all_poets)}")
    total_poems = sum(len(v) for v in poet_poems.values())
    print(f"  Total poems collected: {total_poems}")

    return {"poets": all_poets, "poet_poems": poet_poems}


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Import into our DB
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text, func
from app.core.config import settings
from app.models import Poet, Poem, Verse, Category, PoemCategory
from app.utils.arabic_normalizer import normalizer, arabic_to_slug as _arabic_to_slug

db_engine = create_async_engine(settings.database_url, echo=False)
DbSession = async_sessionmaker(db_engine, expire_on_commit=False)

# Our existing category slugs
CAT_SLUGS = {
    "love", "wisdom", "pride", "elegy", "longing", "description",
    "philosophy", "praise", "nature", "satire", "zuhd", "patriotic",
    "religious", "travel", "war", "apology", "sufi", "occasions", "lament",
}


def make_slug(text: str, suffix: str = "") -> str:
    """Generate a URL-safe slug from Arabic text."""
    try:
        from unidecode import unidecode
        slug = re.sub(r"[^a-z0-9]+", "-", unidecode(text).lower()).strip("-")
    except ImportError:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if suffix:
        slug = f"{slug}-{suffix}"
    return slug[:200] or "poem"


def map_era(era_ar: str) -> str:
    """Map Arabic era name to our era slug."""
    for ar, slug in ERA_MAP.items():
        if ar in era_ar:
            return slug
    return "abbasid"  # default


def map_categories(poem: dict) -> list[str]:
    """Map poem fields to our category slugs."""
    cats = []
    # From theme slug (UUID in qafiyah, but name may help)
    # We don't have theme names here, just slug — default based on era
    era = poem.get("poet_era", "")
    meter = poem.get("poem_meter", "")

    # Heuristic defaults by era
    if "جاهلي" in era or "مخضرم" in era:
        cats.extend(["pride", "description"])
    elif "أموي" in era:
        cats.extend(["love", "pride"])
    elif "عباسي" in era or "أيوبي" in era:
        cats.extend(["praise", "wisdom"])
    elif "أندلسي" in era:
        cats.extend(["love", "description"])
    else:
        cats.extend(["wisdom"])

    return list(set(cats))[:2]


async def ensure_categories(session: AsyncSession) -> dict:
    """Return existing category slug → Category map."""
    result = await session.execute(select(Category))
    cats = result.scalars().all()
    return {c.slug: c for c in cats}


async def unique_poem_slug(session: AsyncSession, slug: str) -> str:
    n = 2
    base = slug[:550]
    while True:
        r = await session.execute(select(Poem.id).where(Poem.slug == slug))
        if r.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


async def import_poet(
    session: AsyncSession,
    poet_data: dict,
    poems_list: list[dict],
    cat_map: dict,
) -> tuple[int, int]:
    """Import one poet + their poems. Skip if already exists."""
    slug = poet_data["slug"]
    name_ar = poet_data.get("name_ar", "")
    if not slug or not name_ar:
        return 0, 0

    # Skip if exists
    existing = (await session.execute(select(Poet.id).where(Poet.slug == slug))).scalar_one_or_none()
    if existing:
        return 0, 0

    era_ar = poet_data.get("era_ar", "")
    era = map_era(era_ar)

    poet = Poet(
        name_ar=name_ar,
        slug=slug,
        bio_ar=poet_data.get("bio_ar", "") or f"شاعر عربي من {era_ar}",
        era=era,
        nationality_ar="عربي",
        is_verified=True,
        metadata_={"type": "faseeh", "source": "qafiyah.com"},
    )
    session.add(poet)
    await session.flush()

    poems_added = 0
    verses_added = 0

    for poem_raw in poems_list[:10]:  # max 10 poems per poet
        title_ar = poem_raw.get("poem_title", "")
        snippet = poem_raw.get("poem_snippet", "")
        meter_ar = poem_raw.get("poem_meter", "")
        poem_slug_raw = poem_raw.get("poem_slug", "")

        if not title_ar or not snippet:
            continue

        verses = parse_snippet(snippet)
        if not verses:
            continue

        # Build full_text
        full_text = "\n".join(
            f"{h1} *** {h2}" if h2 else h1
            for h1, h2 in verses
        )

        # Generate slug
        base_slug = make_slug(title_ar, poem_slug_raw[:8] if poem_slug_raw else "")
        poem_slug = await unique_poem_slug(session, f"{slug}-{base_slug}"[:580])

        poem = Poem(
            poet_id=poet.id,
            title_ar=title_ar,
            slug=poem_slug,
            full_text=full_text,
            meter=METER_MAP.get(meter_ar, meter_ar) or None,
            verse_count=len(verses),
            era=era,
            is_verified=True,
            is_published=True,
            source="qafiyah.com",
            metadata_={"qafiyah_slug": poem_slug_raw},
        )
        session.add(poem)
        await session.flush()

        # Link categories
        for cat_slug in map_categories(poem_raw):
            if cat_slug in cat_map:
                session.add(PoemCategory(poem_id=poem.id, category_id=cat_map[cat_slug].id))

        # Create verses
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
                poet_name_ar=name_ar,
                poet_slug=slug,
                poem_title_ar=title_ar,
                poem_slug=poem_slug,
                is_famous=False,
            ))
            verses_added += 1

        poems_added += 1

    poet.poem_count = poems_added
    poet.verse_count = verses_added
    return poems_added, verses_added


async def import_all(data: dict):
    """Import all fetched data into our DB."""
    print("\n🗄️  Phase 2: Importing into poetry_db...")

    poets_data = data["poets"]
    poet_poems = data["poet_poems"]

    async with DbSession() as session:
        cat_map = await ensure_categories(session)
        print(f"  Categories available: {len(cat_map)}")

        total_poets = total_poems = total_verses = skipped = 0
        poet_slugs = list(poets_data.keys())

        BATCH = 30
        for b_start in range(0, len(poet_slugs), BATCH):
            batch = poet_slugs[b_start:b_start + BATCH]

            for slug in batch:
                poet = poets_data[slug]
                poems = poet_poems.get(slug, [])
                p, v = await import_poet(session, poet, poems, cat_map)
                if p == 0 and v == 0:
                    skipped += 1
                else:
                    total_poets += 1
                    total_poems += p
                    total_verses += v

            await session.commit()
            print(f"  Batch {b_start//BATCH + 1}: {total_poets} poets, {total_poems} poems, {total_verses} verses")

        print(f"\n  ✅ Imported {total_poets} poets, {total_poems} poems, {total_verses} verses")
        print(f"     Skipped {skipped} (already existed)")
        return total_poets, total_poems, total_verses


async def reindex(session):
    """Re-index to Meilisearch."""
    try:
        from meilisearch_python_sdk import AsyncClient
        print("\n📦 Re-indexing Meilisearch...")

        async with AsyncClient(url=settings.meilisearch_url, api_key=settings.meilisearch_key) as client:
            # Verses
            try:
                await client.delete_index("verses")
                await asyncio.sleep(1)
            except Exception:
                pass
            vi = await client.create_index("verses", primary_key="id")
            await vi.update_searchable_attributes([
                "full_verse", "full_verse_normalized", "hemistich_1", "hemistich_2",
                "hemistich_1_normalized", "hemistich_2_normalized",
                "poet_name_ar", "poem_title_ar",
            ])
            await vi.update_filterable_attributes(["poet_id", "poem_id", "is_famous", "poet_slug"])
            await vi.update_sortable_attributes(["view_count"])

            offset = 0
            total = 0
            while True:
                rows = (await session.execute(select(Verse).offset(offset).limit(500))).scalars().all()
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
                total += len(docs)
                offset += 500
                print(f"  Indexed {total} verses...", end="\r")

            print(f"  ✅ Indexed {total} verses        ")

            # Poets
            try:
                await client.delete_index("poets")
                await asyncio.sleep(1)
            except Exception:
                pass
            pi = await client.create_index("poets", primary_key="id")
            poets = (await session.execute(select(Poet))).scalars().all()
            await pi.add_documents([{
                "id": str(p.id), "name_ar": p.name_ar, "name_en": p.name_en or "",
                "slug": p.slug, "era": p.era or "", "bio_ar": (p.bio_ar or "")[:300],
                "poem_count": p.poem_count, "verse_count": p.verse_count,
            } for p in poets])
            print(f"  ✅ Indexed {len(poets)} poets")

    except Exception as e:
        print(f"  ⚠️  Meilisearch failed: {e}")


async def verify(session):
    p = (await session.execute(select(func.count()).select_from(Poet))).scalar()
    po = (await session.execute(select(func.count()).select_from(Poem))).scalar()
    v = (await session.execute(select(func.count()).select_from(Verse))).scalar()
    print("\n" + "=" * 50)
    print("  ✅  IMPORT COMPLETE")
    print("=" * 50)
    print(f"  Poets:   {p:>7,}")
    print(f"  Poems:   {po:>7,}")
    print(f"  Verses:  {v:>7,}")

    era_rows = (await session.execute(
        select(Poet.era, func.count()).group_by(Poet.era).order_by(func.count().desc())
    )).all()
    print("\n  Poets by era:")
    for era, cnt in era_rows:
        print(f"    {era or 'unknown':<20} {cnt:>5}")
    print("=" * 50)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("🌱 Qafiyah → Poetry Platform Importer")

    # ── Phase 1: Fetch (with cache) ──────────────────────────────────────────
    if os.path.exists(CACHE_FILE):
        print(f"\n📂 Loading cached data from {CACHE_FILE}")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  {len(data['poets'])} poets, {sum(len(v) for v in data['poet_poems'].values())} poems")
    else:
        data = await fetch_all_data()
        print(f"\n💾 Saving cache to {CACHE_FILE}")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Phase 2: Import ──────────────────────────────────────────────────────
    # Ensure DB tables exist
    from app.core.database import Base
    import app.models  # noqa
    async with db_engine.begin() as conn:
        for sql in [
            """DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS vector;
               EXCEPTION WHEN OTHERS THEN RAISE WARNING 'pgvector N/A'; END $$""",
        ]:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass
        await conn.run_sync(Base.metadata.create_all)

    total_poets, total_poems, total_verses = await import_all(data)

    async with DbSession() as session:
        if total_verses > 0:
            await reindex(session)
        await verify(session)


if __name__ == "__main__":
    asyncio.run(main())
