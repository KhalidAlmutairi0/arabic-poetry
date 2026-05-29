"""
Import the ARBML/Ashaar dataset — the largest open-source Arabic poetry corpus.
~200K+ verses, ~10K+ poems, ~1K+ poets with meter, era, and theme labels.

Usage:
  python scripts/import_ashaar.py            # download + import
  python scripts/import_ashaar.py --skip-download  # import from cached CSV

Source: https://github.com/ARBML/Ashaar
"""

import asyncio
import sys
import os
import csv
import re
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "ashaar_data")
DATASET_URL = "https://raw.githubusercontent.com/ARBML/Ashaar/main/data/ashaar.csv"
CSV_PATH = os.path.join(DATA_DIR, "ashaar.csv")

# ── Era mapping ──────────────────────────────────────────
ERA_MAP = {
    "العصر الجاهلي": "pre_islamic",
    "عصر صدر الإسلام": "islamic_early",
    "صدر الإسلام": "islamic_early",
    "العصر الأموي": "umayyad",
    "الأموي": "umayyad",
    "العصر العباسي": "abbasid",
    "العباسي": "abbasid",
    "العصر الأندلسي": "andalusian",
    "العصر المملوكي": "mamluk",
    "العصر الأيوبي": "abbasid",
    "العصر الفاطمي": "abbasid",
    "العصر العثماني": "ottoman",
    "العصر الحديث": "modern",
    "الحديث": "modern",
    "العصر المعاصر": "contemporary",
    "المعاصر": "contemporary",
}

# ── Theme → category mapping ─────────────────────────────
THEME_MAP = {
    "غزل": "love",
    "حب": "love",
    "رومانسي": "love",
    "مدح": "praise",
    "رثاء": "elegy",
    "هجاء": "satire",
    "فخر": "pride",
    "حماسة": "pride",
    "وصف": "description",
    "حكمة": "wisdom",
    "زهد": "zuhd",
    "ديني": "religious",
    "إسلامي": "religious",
    "وطني": "patriotic",
    "قومي": "patriotic",
    "سياسي": "patriotic",
    "اعتذار": "apology",
    "عتاب": "apology",
    "شوق": "longing",
    "حنين": "longing",
    "طبيعة": "nature",
}


def download_dataset():
    """Download the Ashaar CSV from GitHub."""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(CSV_PATH):
        size_mb = os.path.getsize(CSV_PATH) / (1024 * 1024)
        logger.info(f"Dataset already exists ({size_mb:.1f} MB). Use --skip-download to reuse.")
        return

    logger.info(f"Downloading Ashaar dataset from GitHub...")
    import urllib.request
    try:
        urllib.request.urlretrieve(DATASET_URL, CSV_PATH)
        size_mb = os.path.getsize(CSV_PATH) / (1024 * 1024)
        logger.info(f"Downloaded {size_mb:.1f} MB to {CSV_PATH}")
    except Exception as e:
        logger.error(f"Download failed: {e}")
        logger.info("Manual download: https://github.com/ARBML/Ashaar")
        logger.info(f"Place the CSV at: {CSV_PATH}")
        sys.exit(1)


def parse_csv() -> list[dict]:
    """Parse the Ashaar CSV into structured poem dicts."""
    logger.info("Parsing CSV...")

    if not os.path.exists(CSV_PATH):
        # Try alternate paths
        alt_paths = [
            os.path.join(DATA_DIR, f)
            for f in os.listdir(DATA_DIR)
            if f.endswith(".csv")
        ] if os.path.exists(DATA_DIR) else []

        if alt_paths:
            csv_path = alt_paths[0]
            logger.info(f"Using alternate CSV: {csv_path}")
        else:
            logger.error(f"CSV not found at {CSV_PATH}")
            logger.info("Run without --skip-download first, or place CSV manually.")
            sys.exit(1)
    else:
        csv_path = CSV_PATH

    poems = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        logger.info(f"CSV columns: {columns}")

        for row in reader:
            # The Ashaar dataset has columns like:
            # poet_name, poem_title, poem_text, meter, era, theme
            # Column names may vary — handle flexibly
            poet_name = (
                row.get("poet_name", "")
                or row.get("poet", "")
                or row.get("الشاعر", "")
                or ""
            ).strip()

            title = (
                row.get("poem_title", "")
                or row.get("title", "")
                or row.get("عنوان", "")
                or ""
            ).strip()

            text = (
                row.get("poem_text", "")
                or row.get("text", "")
                or row.get("القصيدة", "")
                or row.get("verses", "")
                or ""
            ).strip()

            meter = (
                row.get("meter", "")
                or row.get("البحر", "")
                or ""
            ).strip()

            era = (
                row.get("era", "")
                or row.get("العصر", "")
                or ""
            ).strip()

            theme = (
                row.get("theme", "")
                or row.get("الغرض", "")
                or row.get("genre", "")
                or ""
            ).strip()

            if not poet_name or not text:
                continue

            if not title:
                first_line = text.split("\n")[0][:60]
                title = first_line if first_line else "قصيدة"

            poems.append({
                "poet_name": poet_name,
                "title": title,
                "text": text,
                "meter": meter if meter and meter != "nan" else None,
                "era": era,
                "theme": theme,
            })

    logger.info(f"Parsed {len(poems)} poems")
    return poems


def parse_verses(text: str) -> list[tuple[str, str]]:
    """Parse poem text into hemistich pairs."""
    verses = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines:
        # Try common separators: *** , \t, multiple spaces
        parts = None
        for sep in ["***", "\t", "   ", "  "]:
            if sep in line:
                parts = [p.strip() for p in line.split(sep, 1) if p.strip()]
                break

        if parts and len(parts) == 2:
            h1, h2 = parts
        else:
            h1 = line
            h2 = ""

        if len(h1) > 2:
            verses.append((h1, h2))

    return verses[:100]  # max 100 verses per poem


def map_era(era_str: str) -> str:
    if not era_str:
        return "abbasid"
    for ar, slug in ERA_MAP.items():
        if ar in era_str:
            return slug
    return "abbasid"


def map_theme(theme_str: str) -> list[str]:
    if not theme_str:
        return ["wisdom"]
    cats = []
    for ar, slug in THEME_MAP.items():
        if ar in theme_str:
            cats.append(slug)
    return cats[:2] if cats else ["wisdom"]


async def import_to_db(poems: list[dict]):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select, text
    from app.core.config import settings
    from app.core.database import Base
    from app.models import Poet, Poem, Verse, Category, PoemCategory
    from app.utils.arabic_normalizer import normalizer
    import app.models  # noqa

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Ensure tables exist
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        # Load existing data
        cat_rows = (await session.execute(select(Category))).scalars().all()
        cat_map = {c.slug: c for c in cat_rows}

        existing_poet_slugs = set(
            row[0] for row in (await session.execute(select(Poet.slug))).fetchall()
        )
        existing_poem_slugs = set(
            row[0] for row in (await session.execute(select(Poem.slug))).fetchall()
        )

        logger.info(f"Existing: {len(existing_poet_slugs)} poets, {len(existing_poem_slugs)} poems")
        logger.info(f"Categories: {len(cat_map)}")

        # Group poems by poet
        poet_poems: dict[str, list[dict]] = {}
        for p in poems:
            name = p["poet_name"]
            if name not in poet_poems:
                poet_poems[name] = []
            poet_poems[name].append(p)

        logger.info(f"Unique poets in dataset: {len(poet_poems)}")

        added_poets = 0
        added_poems = 0
        added_verses = 0
        skipped_poems = 0

        def make_slug(text: str) -> str:
            try:
                from unidecode import unidecode
                slug = re.sub(r"[^a-z0-9]+", "-", unidecode(text).lower()).strip("-")
            except ImportError:
                slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
            return slug[:200] or "unknown"

        for poet_idx, (poet_name, poet_poem_list) in enumerate(poet_poems.items(), 1):
            poet_slug = make_slug(poet_name)

            if poet_slug in existing_poet_slugs:
                # Poet exists — still add new poems
                poet_row = (await session.execute(
                    select(Poet).where(Poet.slug == poet_slug)
                )).scalar_one_or_none()
                if not poet_row:
                    continue
            else:
                era_sample = poet_poem_list[0].get("era", "")
                poet_row = Poet(
                    name_ar=poet_name,
                    slug=poet_slug,
                    bio_ar=f"شاعر عربي",
                    era=map_era(era_sample),
                    nationality_ar="عربي",
                    is_verified=True,
                    metadata_={"source": "ashaar"},
                )
                session.add(poet_row)
                await session.flush()
                existing_poet_slugs.add(poet_slug)
                added_poets += 1

            poems_for_this_poet = 0
            verses_for_this_poet = 0

            for poem_data in poet_poem_list[:30]:  # max 30 poems per poet
                title = poem_data["title"]
                poem_slug = f"{poet_slug}-{make_slug(title)}"[:580]

                if poem_slug in existing_poem_slugs:
                    skipped_poems += 1
                    continue

                verses = parse_verses(poem_data["text"])
                if not verses:
                    continue

                full_text = "\n".join(
                    f"{h1} *** {h2}" if h2 else h1 for h1, h2 in verses
                )

                poem = Poem(
                    poet_id=poet_row.id,
                    title_ar=title,
                    slug=poem_slug,
                    full_text=full_text,
                    meter=poem_data.get("meter"),
                    verse_count=len(verses),
                    era=map_era(poem_data.get("era", "")),
                    is_verified=True,
                    is_published=True,
                    source="ashaar/ARBML",
                    metadata_={"theme": poem_data.get("theme", "")},
                )
                session.add(poem)
                await session.flush()
                existing_poem_slugs.add(poem_slug)

                # Categories
                for cat_slug in map_theme(poem_data.get("theme", "")):
                    if cat_slug in cat_map:
                        session.add(PoemCategory(
                            poem_id=poem.id,
                            category_id=cat_map[cat_slug].id,
                        ))

                # Verses
                for pos, (h1, h2) in enumerate(verses, 1):
                    full_verse = f"{h1} *** {h2}" if h2 else h1
                    session.add(Verse(
                        poem_id=poem.id,
                        poet_id=poet_row.id,
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
                poems_for_this_poet += 1
                verses_for_this_poet += len(verses)

            # Update poet counts
            poet_row.poem_count = (poet_row.poem_count or 0) + poems_for_this_poet
            poet_row.verse_count = (poet_row.verse_count or 0) + verses_for_this_poet

            # Commit in batches
            if poet_idx % 50 == 0:
                await session.commit()
                logger.info(
                    f"  [{poet_idx}/{len(poet_poems)}] "
                    f"+{added_poets} poets, +{added_poems} poems, +{added_verses} verses"
                )

        await session.commit()

        logger.info("=" * 60)
        logger.info(f"  IMPORT COMPLETE")
        logger.info(f"  New poets:  {added_poets}")
        logger.info(f"  New poems:  {added_poems}")
        logger.info(f"  New verses: {added_verses}")
        logger.info(f"  Skipped:    {skipped_poems} (already existed)")
        logger.info("=" * 60)


async def reindex_meilisearch():
    """Full reindex of all verses and poets to Meilisearch."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.core.config import settings
    from app.models import Poet, Verse

    try:
        from meilisearch_python_sdk import AsyncClient
    except ImportError:
        logger.warning("meilisearch-python-sdk not installed, skipping reindex")
        return

    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    logger.info("Re-indexing Meilisearch...")

    async with Session() as session:
        async with AsyncClient(url=settings.meilisearch_url, api_key=settings.meilisearch_key) as client:
            # Verses
            vi = client.index("verses")
            offset = 0
            total = 0
            while True:
                rows = (await session.execute(
                    select(Verse).offset(offset).limit(1000)
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
                total += len(docs)
                offset += 1000
                if total % 5000 == 0:
                    logger.info(f"  Indexed {total} verses...")

            logger.info(f"  Indexed {total} verses total")

            # Poets
            pi = client.index("poets")
            poets = (await session.execute(select(Poet))).scalars().all()
            if poets:
                await pi.add_documents([{
                    "id": str(p.id), "name_ar": p.name_ar, "name_en": p.name_en or "",
                    "slug": p.slug, "era": p.era or "", "bio_ar": (p.bio_ar or "")[:300],
                    "poem_count": p.poem_count, "verse_count": p.verse_count,
                } for p in poets])
                logger.info(f"  Indexed {len(poets)} poets")


async def main():
    t0 = time.time()
    skip_download = "--skip-download" in sys.argv

    if not skip_download:
        download_dataset()

    poems = parse_csv()
    await import_to_db(poems)
    await reindex_meilisearch()

    logger.info(f"Total time: {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    asyncio.run(main())
