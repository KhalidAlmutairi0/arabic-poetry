"""
Import data from the Qafiyah GitHub repo dump into our platform.

Pipeline:
1. Download the pg_dump from GitHub (if not cached locally)
2. Restore it into a temp PostgreSQL container
3. Read poets, poems, verses, meters, eras, themes from the restored DB
4. Transform and insert into our platform's DB schema
5. Index everything into Meilisearch

Run:
    cd backend
    python -X utf8 scripts/import_qafiyah.py

Requires: Docker running, platform DB running (docker-compose up postgres redis meilisearch)
"""

import asyncio
import os
import sys
import subprocess
import time
import json
import logging
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DUMP_URL = "https://github.com/alwalxed/qafiyah/raw/main/dumps/0031_26_05_2026/qafiyah_public_20260526_013039.dump"
DUMP_DIR = os.path.join(os.path.dirname(__file__), "data")
DUMP_FILE = os.path.join(DUMP_DIR, "qafiyah_dump.dump")

TEMP_CONTAINER = "qafiyah_temp_pg"
TEMP_DB = "qafiyah"
TEMP_USER = "qafiyah"
TEMP_PASS = "qafiyah_temp"
TEMP_PORT = 5433

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Download dump
# ─────────────────────────────────────────────────────────────────────────────

def download_dump():
    if os.path.exists(DUMP_FILE):
        size = os.path.getsize(DUMP_FILE)
        if size > 1_000_000:
            logger.info(f"Dump already cached ({size / 1e6:.1f} MB): {DUMP_FILE}")
            return
        logger.info("Dump file too small, re-downloading...")

    os.makedirs(DUMP_DIR, exist_ok=True)
    logger.info(f"Downloading dump from GitHub...")
    logger.info(f"  URL: {DUMP_URL}")

    import urllib.request
    urllib.request.urlretrieve(DUMP_URL, DUMP_FILE)
    size = os.path.getsize(DUMP_FILE)
    logger.info(f"  Downloaded: {size / 1e6:.1f} MB")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Start temp PostgreSQL + restore dump
# ─────────────────────────────────────────────────────────────────────────────

def start_temp_postgres():
    # Kill existing container if any
    subprocess.run(
        ["docker", "rm", "-f", TEMP_CONTAINER],
        capture_output=True,
    )

    logger.info("Starting temporary PostgreSQL 17 container...")
    subprocess.run(
        [
            "docker", "run", "-d",
            "--name", TEMP_CONTAINER,
            "-e", f"POSTGRES_USER={TEMP_USER}",
            "-e", f"POSTGRES_PASSWORD={TEMP_PASS}",
            "-e", f"POSTGRES_DB={TEMP_DB}",
            "-p", f"{TEMP_PORT}:5432",
            "postgres:17-alpine",
        ],
        check=True,
    )

    # Wait for PostgreSQL to be ready
    logger.info("Waiting for PostgreSQL to be ready...")
    for i in range(30):
        result = subprocess.run(
            ["docker", "exec", TEMP_CONTAINER, "pg_isready", "-U", TEMP_USER],
            capture_output=True,
        )
        if result.returncode == 0:
            logger.info("  PostgreSQL ready!")
            return
        time.sleep(1)
    raise RuntimeError("PostgreSQL didn't start in time")


def restore_dump():
    logger.info("Restoring dump into temp container...")

    # Copy dump file into container
    subprocess.run(
        ["docker", "cp", DUMP_FILE, f"{TEMP_CONTAINER}:/tmp/qafiyah.dump"],
        check=True,
    )

    # Restore
    result = subprocess.run(
        [
            "docker", "exec", TEMP_CONTAINER,
            "pg_restore", "-U", TEMP_USER, "-d", TEMP_DB,
            "--no-owner", "--no-privileges",
            "/tmp/qafiyah.dump",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 and "error" in result.stderr.lower():
        # pg_restore often returns non-zero for warnings, which is OK
        critical = [l for l in result.stderr.split("\n") if "FATAL" in l or "could not" in l.lower()]
        if critical:
            logger.error(f"Restore errors: {result.stderr[:500]}")
            raise RuntimeError("Dump restore failed")

    logger.info("  Dump restored successfully")


def stop_temp_postgres():
    logger.info("Cleaning up temp container...")
    subprocess.run(["docker", "rm", "-f", TEMP_CONTAINER], capture_output=True)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Read data from Qafiyah DB
# ─────────────────────────────────────────────────────────────────────────────

async def read_qafiyah_data() -> dict:
    """Connect to the temp Qafiyah DB and read all data."""
    import asyncpg

    conn = await asyncpg.connect(
        host="localhost",
        port=TEMP_PORT,
        user=TEMP_USER,
        password=TEMP_PASS,
        database=TEMP_DB,
    )

    try:
        # List tables to understand schema
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        table_names = [t["tablename"] for t in tables]
        logger.info(f"  Tables found: {table_names}")

        # Read eras
        eras = {}
        if "eras" in table_names:
            rows = await conn.fetch("SELECT * FROM eras")
            for r in rows:
                eras[r["id"]] = dict(r)
            logger.info(f"  Eras: {len(eras)}")

        # Read meters
        meters = {}
        if "meters" in table_names:
            rows = await conn.fetch("SELECT * FROM meters")
            for r in rows:
                meters[r["id"]] = dict(r)
            logger.info(f"  Meters: {len(meters)}")

        # Read themes
        themes = {}
        if "themes" in table_names:
            rows = await conn.fetch("SELECT * FROM themes")
            for r in rows:
                themes[r["id"]] = dict(r)
            logger.info(f"  Themes: {len(themes)}")

        # Read poets
        poets = []
        if "poets" in table_names:
            rows = await conn.fetch("SELECT * FROM poets ORDER BY id")
            poets = [dict(r) for r in rows]
            logger.info(f"  Poets: {len(poets)}")

        # Read poems with content
        poems = []
        if "poems" in table_names:
            rows = await conn.fetch("""
                SELECT p.*,
                       pt.name as poet_name, pt.slug as poet_slug,
                       m.name as meter_name,
                       t.name as theme_name,
                       e.name as era_name
                FROM poems p
                LEFT JOIN poets pt ON p.poet_id = pt.id
                LEFT JOIN meters m ON p.meter_id = m.id
                LEFT JOIN themes t ON p.theme_id = t.id
                LEFT JOIN eras e ON pt.era_id = e.id
                ORDER BY p.id
            """)
            poems = [dict(r) for r in rows]
            logger.info(f"  Poems: {len(poems)}")

        return {
            "eras": eras,
            "meters": meters,
            "themes": themes,
            "poets": poets,
            "poems": poems,
        }
    finally:
        await conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Transform + import into our platform DB
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text, func
from app.core.config import settings
from app.models import Poet, Poem, Verse, Category, PoemCategory
from app.utils.arabic_normalizer import normalizer, arabic_to_slug

platform_engine = create_async_engine(settings.database_url, echo=False)
PlatformSession = async_sessionmaker(platform_engine, expire_on_commit=False)

ERA_MAP = {
    "جاهلي": "pre_islamic",
    "إسلامي": "islamic_early",
    "أموي": "umayyad",
    "عباسي": "abbasid",
    "أندلسي": "andalusian",
    "مملوكي": "mamluk",
    "عثماني": "ottoman",
    "حديث": "modern",
    "معاصر": "contemporary",
}

THEME_TO_CATEGORY = {
    "غزل": "love",
    "حكمة": "wisdom",
    "فخر": "pride",
    "رثاء": "elegy",
    "مدح": "praise",
    "هجاء": "satire",
    "وصف": "description",
    "زهد": "philosophy",
    "حماسة": "pride",
}


def parse_verses_from_content(content: str) -> list[dict]:
    """
    Parse Qafiyah poem content into individual verses.
    Content format: verses separated by newlines, hemistiches separated by various markers.
    """
    if not content:
        return []

    verses = []
    lines = content.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 4:
            continue

        # Try to split into hemistiches
        h1, h2 = "", ""

        # Common separators: *** | *** | tab | multiple spaces
        for sep in ["***", "\t", "    ", " * "]:
            if sep in line:
                parts = line.split(sep, 1)
                h1 = parts[0].strip()
                h2 = parts[1].strip() if len(parts) > 1 else ""
                break

        if not h1:
            # No separator found — whole line is the verse
            h1 = line
            h2 = ""

        if len(h1) < 3:
            continue

        full_verse = f"{h1} *** {h2}" if h2 else h1

        verses.append({
            "hemistich_1": h1,
            "hemistich_2": h2 if h2 else None,
            "full_verse": full_verse,
        })

    return verses


def map_era(era_name: str) -> str:
    if not era_name:
        return "abbasid"
    for ar, slug in ERA_MAP.items():
        if ar in era_name:
            return slug
    return "abbasid"


async def ensure_tables():
    """Create tables if they don't exist."""
    from app.core.database import Base
    import app.models  # noqa
    async with platform_engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Platform tables ready")


async def ensure_categories(session: AsyncSession) -> dict[str, "Category"]:
    """Create default categories if they don't exist."""
    from app.models import Category

    CATEGORIES = [
        {"name_ar": "الغزل والحب", "name_en": "Love", "slug": "love", "icon": "❤️", "color": "#E74C3C", "display_order": 1},
        {"name_ar": "الحكمة", "name_en": "Wisdom", "slug": "wisdom", "icon": "🌙", "color": "#8E44AD", "display_order": 2},
        {"name_ar": "الفخر", "name_en": "Pride", "slug": "pride", "icon": "⚔️", "color": "#E67E22", "display_order": 3},
        {"name_ar": "الرثاء", "name_en": "Elegy", "slug": "elegy", "icon": "🕊️", "color": "#95A5A6", "display_order": 4},
        {"name_ar": "الشوق والحنين", "name_en": "Longing", "slug": "longing", "icon": "🌊", "color": "#3498DB", "display_order": 5},
        {"name_ar": "الوصف", "name_en": "Description", "slug": "description", "icon": "🌿", "color": "#27AE60", "display_order": 6},
        {"name_ar": "الفلسفة", "name_en": "Philosophy", "slug": "philosophy", "icon": "⚡", "color": "#2C3E50", "display_order": 7},
        {"name_ar": "المدح", "name_en": "Praise", "slug": "praise", "icon": "👑", "color": "#F1C40F", "display_order": 8},
        {"name_ar": "الطبيعة", "name_en": "Nature", "slug": "nature", "icon": "🌸", "color": "#1ABC9C", "display_order": 9},
        {"name_ar": "الهجاء", "name_en": "Satire", "slug": "satire", "icon": "🗡️", "color": "#C0392B", "display_order": 10},
    ]

    cat_map = {}
    for cat_data in CATEGORIES:
        result = await session.execute(select(Category).where(Category.slug == cat_data["slug"]))
        existing = result.scalar_one_or_none()
        if existing:
            cat_map[cat_data["slug"]] = existing
        else:
            cat = Category(**cat_data)
            session.add(cat)
            await session.flush()
            cat_map[cat_data["slug"]] = cat

    await session.commit()
    logger.info(f"Categories ready: {len(cat_map)}")
    return cat_map


async def import_into_platform(qdata: dict):
    """Transform Qafiyah data and insert into our platform."""
    async with PlatformSession() as session:
        cat_map = await ensure_categories(session)

        # Get existing poet slugs to avoid duplicates
        existing_poet_slugs = set()
        rows = await session.execute(select(Poet.slug))
        for row in rows.fetchall():
            existing_poet_slugs.add(row[0])

        # Get existing poem slugs
        existing_poem_slugs = set()
        rows = await session.execute(select(Poem.slug))
        for row in rows.fetchall():
            existing_poem_slugs.add(row[0])

        logger.info(f"Existing: {len(existing_poet_slugs)} poets, {len(existing_poem_slugs)} poems")

        # ── Import poets ──────────────────────────────────
        poet_id_map = {}  # qafiyah_id → our poet
        poets_created = 0

        # First, map existing poets by slug
        existing_poets_result = await session.execute(select(Poet))
        for poet in existing_poets_result.scalars().all():
            # Try to match by slug
            for qp in qdata["poets"]:
                if qp.get("slug") == poet.slug:
                    poet_id_map[qp["id"]] = poet
                    break

        for qp in qdata["poets"]:
            if qp["id"] in poet_id_map:
                continue

            slug = qp.get("slug", "")
            name_ar = qp.get("name", "")
            if not name_ar or not slug:
                continue

            if slug in existing_poet_slugs:
                # Slug collision — find and reuse
                result = await session.execute(select(Poet).where(Poet.slug == slug))
                existing = result.scalar_one_or_none()
                if existing:
                    poet_id_map[qp["id"]] = existing
                    continue

            era_id = qp.get("era_id")
            era_name = ""
            if era_id and era_id in qdata["eras"]:
                era_name = qdata["eras"][era_id].get("name", "")

            poet = Poet(
                name_ar=name_ar,
                slug=slug,
                bio_ar=f"شاعر عربي من العصر {era_name}" if era_name else "شاعر عربي",
                era=map_era(era_name),
                nationality_ar="عربي",
                is_verified=True,
                metadata_={"source": "qafiyah", "qafiyah_id": qp["id"]},
            )
            session.add(poet)
            await session.flush()
            poet_id_map[qp["id"]] = poet
            existing_poet_slugs.add(slug)
            poets_created += 1

        await session.commit()
        logger.info(f"Poets: {poets_created} created, {len(poet_id_map)} total mapped")

        # ── Import poems + verses ─────────────────────────
        poems_created = 0
        verses_created = 0
        BATCH_SIZE = 100

        for batch_start in range(0, len(qdata["poems"]), BATCH_SIZE):
            batch = qdata["poems"][batch_start:batch_start + BATCH_SIZE]

            for qpoem in batch:
                slug = qpoem.get("slug", "")
                title = qpoem.get("title", "")
                content = qpoem.get("content", "")
                poet_slug = qpoem.get("poet_slug", "")
                poet_id_q = qpoem.get("poet_id")

                if not slug or not title or not content:
                    continue

                if slug in existing_poem_slugs:
                    continue

                # Find our poet
                poet = poet_id_map.get(poet_id_q)
                if not poet:
                    continue

                # Parse verses from content
                verses_data = parse_verses_from_content(content)
                if not verses_data:
                    continue

                # Map theme to category
                theme_name = qpoem.get("theme_name", "")
                category_slug = None
                for ar_theme, cat_slug in THEME_TO_CATEGORY.items():
                    if ar_theme in (theme_name or ""):
                        category_slug = cat_slug
                        break

                meter_name = qpoem.get("meter_name", "")
                era_name = qpoem.get("era_name", "")
                verse_count = qpoem.get("verse_count", len(verses_data))

                poem = Poem(
                    poet_id=poet.id,
                    title_ar=title,
                    slug=slug,
                    full_text=content,
                    meter=meter_name or None,
                    era=map_era(era_name),
                    verse_count=len(verses_data),
                    is_verified=True,
                    is_published=True,
                    metadata_={"source": "qafiyah", "qafiyah_slug": slug},
                )
                session.add(poem)
                await session.flush()

                # Attach category
                if category_slug and category_slug in cat_map:
                    pc = PoemCategory(
                        poem_id=poem.id,
                        category_id=cat_map[category_slug].id,
                    )
                    session.add(pc)

                # Create verses
                for i, vd in enumerate(verses_data, start=1):
                    h1 = vd["hemistich_1"]
                    h2 = vd["hemistich_2"]
                    full = vd["full_verse"]

                    verse = Verse(
                        poem_id=poem.id,
                        poet_id=poet.id,
                        position=i,
                        hemistich_1=h1,
                        hemistich_2=h2,
                        full_verse=full,
                        full_verse_normalized=normalizer.normalize(full),
                        hemistich_1_normalized=normalizer.normalize(h1),
                        hemistich_2_normalized=normalizer.normalize(h2) if h2 else None,
                        poet_name_ar=poet.name_ar,
                        poet_slug=poet.slug,
                        poem_title_ar=title,
                        poem_slug=slug,
                        is_famous=False,
                    )
                    session.add(verse)
                    verses_created += 1

                # Update poet counts
                poet.poem_count = (poet.poem_count or 0) + 1
                poet.verse_count = (poet.verse_count or 0) + len(verses_data)

                existing_poem_slugs.add(slug)
                poems_created += 1

            await session.commit()
            logger.info(
                f"  Progress: {min(batch_start + BATCH_SIZE, len(qdata['poems']))}/{len(qdata['poems'])} "
                f"| +{poems_created} poems, +{verses_created} verses"
            )

        logger.info(f"Import complete: {poems_created} poems, {verses_created} verses")
        return poems_created, verses_created


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Index to Meilisearch
# ─────────────────────────────────────────────────────────────────────────────

async def index_all_to_meilisearch():
    """Index all verses and poets to Meilisearch."""
    from meilisearch_python_sdk import AsyncClient
    from sqlalchemy import select

    logger.info("Indexing to Meilisearch...")

    async with PlatformSession() as session:
        async with AsyncClient(
            url=settings.meilisearch_url,
            api_key=settings.meilisearch_key,
        ) as client:
            # Index verses in batches
            total_verses = (await session.execute(
                select(func.count(Verse.id))
            )).scalar_one()
            logger.info(f"  Total verses to index: {total_verses}")

            BATCH = 5000
            offset = 0
            indexed = 0

            while offset < total_verses:
                result = await session.execute(
                    select(Verse)
                    .order_by(Verse.id)
                    .limit(BATCH)
                    .offset(offset)
                )
                verses = list(result.scalars().all())
                if not verses:
                    break

                docs = [
                    {
                        "id": str(v.id),
                        "full_verse": v.full_verse,
                        "full_verse_normalized": v.full_verse_normalized or "",
                        "hemistich_1": v.hemistich_1,
                        "hemistich_2": v.hemistich_2 or "",
                        "hemistich_1_normalized": v.hemistich_1_normalized or "",
                        "hemistich_2_normalized": v.hemistich_2_normalized or "",
                        "poet_name_ar": v.poet_name_ar or "",
                        "poet_slug": v.poet_slug or "",
                        "poem_title_ar": v.poem_title_ar or "",
                        "poem_slug": v.poem_slug or "",
                        "poet_id": str(v.poet_id),
                        "poem_id": str(v.poem_id),
                        "is_famous": v.is_famous,
                        "view_count": v.view_count or 0,
                    }
                    for v in verses
                ]

                verses_index = client.index("verses")
                await verses_index.add_documents(docs, primary_key="id")
                indexed += len(docs)
                offset += BATCH
                logger.info(f"  Verses indexed: {indexed}/{total_verses}")

            # Index poets
            result = await session.execute(select(Poet))
            poets = list(result.scalars().all())

            poet_docs = [
                {
                    "id": str(p.id),
                    "name_ar": p.name_ar,
                    "name_en": p.name_en or "",
                    "slug": p.slug,
                    "era": p.era or "",
                    "poem_count": p.poem_count or 0,
                    "verse_count": p.verse_count or 0,
                }
                for p in poets
            ]

            if poet_docs:
                poets_index = client.index("poets")
                await poets_index.add_documents(poet_docs, primary_key="id")
                logger.info(f"  Poets indexed: {len(poet_docs)}")

            # Index poems
            from sqlalchemy.orm import selectinload
            result = await session.execute(
                select(Poem).options(selectinload(Poem.poet))
            )
            poems = list(result.scalars().all())

            poem_docs = [
                {
                    "id": str(p.id),
                    "title_ar": p.title_ar,
                    "title_en": p.title_en or "",
                    "slug": p.slug,
                    "poet_id": str(p.poet_id),
                    "poet_name_ar": p.poet.name_ar if p.poet else "",
                    "era": p.era or "",
                    "meter": p.meter or "",
                    "verse_count": p.verse_count or 0,
                    "view_count": p.view_count or 0,
                }
                for p in poems
            ]

            if poem_docs:
                for i in range(0, len(poem_docs), 5000):
                    batch = poem_docs[i:i + 5000]
                    poems_index = client.index("poems")
                    await poems_index.add_documents(batch, primary_key="id")
                logger.info(f"  Poems indexed: {len(poem_docs)}")

    logger.info("Meilisearch indexing complete!")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    logger.info("=" * 60)
    logger.info("Qafiyah Data Import Pipeline")
    logger.info("=" * 60)

    # Step 1: Download
    download_dump()

    # Step 2: Start temp DB + restore
    start_temp_postgres()
    try:
        restore_dump()

        # Step 3: Read data
        logger.info("\nReading data from Qafiyah DB...")
        qdata = await read_qafiyah_data()

        # Step 4: Import into platform
        logger.info("\nImporting into platform DB...")
        await ensure_tables()
        poems_count, verses_count = await import_into_platform(qdata)

        # Step 5: Index to Meilisearch
        if poems_count > 0:
            try:
                await index_all_to_meilisearch()
            except Exception as e:
                logger.warning(f"Meilisearch indexing failed (non-critical): {e}")
                logger.info("You can re-run indexing later when Meilisearch is available.")

    finally:
        stop_temp_postgres()

    logger.info("\n" + "=" * 60)
    logger.info("Import complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
