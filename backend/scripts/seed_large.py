"""
Large-scale seed script — 1000+ poets, 5000+ poems, 30000+ verses.

Run from backend root:
    python -X utf8 scripts/seed_large.py

Strategy:
- Idempotent: skips poets/poems whose slug already exists
- Batches of 50 poets to avoid session bloat
- Full Meilisearch re-index at end
- Verification report at end
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text, func
from app.core.config import settings
from app.models import Poet, Poem, Verse, Category, PoemCategory
from app.utils.arabic_normalizer import normalizer, arabic_to_slug
import uuid

engine = create_async_engine(settings.database_url, echo=False)
Session = async_sessionmaker(engine, expire_on_commit=False)


# ── Import data modules ────────────────────────────────────────────────────────

from scripts.data.categories_data import ALL_CATEGORIES
from scripts.data.faseeh_poets_data import FASEEH_POETS
from scripts.data.nabati_poets_data import NABATI_POETS

ALL_POETS = FASEEH_POETS + NABATI_POETS


# ── Categories ─────────────────────────────────────────────────────────────────

async def seed_categories(session: AsyncSession) -> dict:
    """Upsert all categories. Returns slug -> Category map."""
    print("\n📂 Seeding categories...")
    cat_map = {}

    for cat_data in ALL_CATEGORIES:
        result = await session.execute(
            select(Category).where(Category.slug == cat_data["slug"])
        )
        cat = result.scalar_one_or_none()
        if cat is None:
            cat = Category(**cat_data)
            session.add(cat)
            await session.flush()
        cat_map[cat_data["slug"]] = cat

    await session.commit()
    print(f"  ✅ {len(cat_map)} categories ready")
    return cat_map


# ── Single poet seeder ─────────────────────────────────────────────────────────

async def _unique_poem_slug(session: AsyncSession, base_slug: str) -> str:
    """Ensure poem slug is unique — append -2, -3 etc. if needed."""
    slug = base_slug[:580]
    n = 2
    while True:
        result = await session.execute(select(Poem).where(Poem.slug == slug))
        if result.scalar_one_or_none() is None:
            return slug
        slug = f"{base_slug[:570]}-{n}"
        n += 1


async def seed_poet(session: AsyncSession, raw: dict, cat_map: dict) -> tuple[int, int]:
    """
    Seed one poet + their poems + verses.
    Returns (poems_added, verses_added). Returns (0, 0) if poet already exists.
    """
    # Deep-copy so we don't mutate the module-level list
    poet_data = {k: v for k, v in raw.items() if k != "poems"}
    poems_raw = raw.get("poems", [])

    # Skip if already exists
    result = await session.execute(
        select(Poet).where(Poet.slug == poet_data["slug"])
    )
    if result.scalar_one_or_none() is not None:
        return 0, 0

    # Handle both "metadata" and "metadata_" keys from data files
    metadata = poet_data.pop("metadata_", None) or poet_data.pop("metadata", {})
    poet = Poet(**poet_data, metadata_=metadata)
    session.add(poet)
    await session.flush()

    poems_added = 0
    verses_added = 0

    for poem_raw in poems_raw:
        pd = dict(poem_raw)
        verses_list = pd.pop("verses", [])
        cat_slugs = pd.pop("categories", [])

        # Build full_text
        full_text = "\n".join(
            f"{v['h1']} *** {v['h2']}" if v.get("h2") else v["h1"]
            for v in verses_list
        )

        # Slug
        raw_slug = pd.pop("slug", None) or arabic_to_slug(pd.get("title_ar", "poem"))
        poem_slug = await _unique_poem_slug(session, f"{poet.slug}-{raw_slug}"[:580])

        poem = Poem(
            poet_id=poet.id,
            full_text=full_text,
            slug=poem_slug,
            era=pd.get("era", poet.era),
            is_verified=pd.get("is_verified", poet.is_verified),
            is_published=True,
            **{k: v for k, v in pd.items() if k not in ("era", "is_verified", "is_published")},
        )
        session.add(poem)
        await session.flush()

        # Link categories
        for slug in cat_slugs:
            if slug in cat_map:
                session.add(PoemCategory(poem_id=poem.id, category_id=cat_map[slug].id))

        # Create verses
        for pos, vd in enumerate(verses_list, 1):
            h1 = vd["h1"]
            h2 = vd.get("h2", "") or ""
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
                poet_name_ar=poet.name_ar,
                poet_slug=poet.slug,
                poem_title_ar=poem.title_ar,
                poem_slug=poem.slug,
                is_famous=vd.get("famous", False),
            ))
            verses_added += 1

        poem.verse_count = len(verses_list)
        poems_added += 1

    poet.poem_count = poems_added
    poet.verse_count = verses_added
    return poems_added, verses_added


# ── Batch seeder ───────────────────────────────────────────────────────────────

async def seed_all_poets(session: AsyncSession, cat_map: dict):
    total = len(ALL_POETS)
    print(f"\n📖 Seeding {total} poets in batches of 50...")

    done_poets = skipped = total_poems = total_verses = 0
    t0 = time.time()
    BATCH = 50

    for b_start in range(0, total, BATCH):
        batch = ALL_POETS[b_start:b_start + BATCH]
        for idx, raw in enumerate(batch, b_start + 1):
            print(f"  [{idx:>4}/{total}] {raw['name_ar'][:30]:<30}", end="\r", flush=True)
            p, v = await seed_poet(session, raw, cat_map)
            if p == 0:
                skipped += 1
            else:
                done_poets += 1
                total_poems += p
                total_verses += v

        await session.commit()
        elapsed = time.time() - t0
        print(f"  Batch {b_start//BATCH + 1:>2}: {done_poets} new poets, "
              f"{total_poems} poems, {total_verses} verses  ({elapsed:.0f}s)")

    print(f"\n  ✅ Added {done_poets} poets, {total_poems} poems, {total_verses} verses")
    print(f"     (Skipped {skipped} already-existing poets)")
    return done_poets, total_poems, total_verses


# ── Meilisearch re-index ───────────────────────────────────────────────────────

async def reindex_meilisearch(session: AsyncSession):
    try:
        from meilisearch_python_sdk import AsyncClient
        print("\n📦 Re-indexing Meilisearch...")

        async with AsyncClient(url=settings.meilisearch_url, api_key=settings.meilisearch_key) as client:

            # ── Verses ──
            try:
                await client.delete_index("verses")
                await asyncio.sleep(1)
            except Exception:
                pass

            vi = await client.create_index("verses", primary_key="id")
            await vi.update_searchable_attributes([
                "full_verse", "full_verse_normalized",
                "hemistich_1", "hemistich_2",
                "hemistich_1_normalized", "hemistich_2_normalized",
                "poet_name_ar", "poem_title_ar",
            ])
            await vi.update_filterable_attributes(["poet_id", "poem_id", "is_famous", "poet_slug"])
            await vi.update_sortable_attributes(["view_count"])

            offset = 0
            chunk = 500
            indexed = 0
            while True:
                rows = (await session.execute(
                    select(Verse).offset(offset).limit(chunk)
                )).scalars().all()
                if not rows:
                    break
                docs = [{
                    "id": str(v.id),
                    "full_verse": v.full_verse,
                    "full_verse_normalized": v.full_verse_normalized or v.full_verse,
                    "hemistich_1": v.hemistich_1,
                    "hemistich_2": v.hemistich_2 or "",
                    "hemistich_1_normalized": v.hemistich_1_normalized or v.hemistich_1,
                    "hemistich_2_normalized": v.hemistich_2_normalized or "",
                    "poet_name_ar": v.poet_name_ar or "",
                    "poet_slug": v.poet_slug or "",
                    "poem_title_ar": v.poem_title_ar or "",
                    "poem_slug": v.poem_slug or "",
                    "poet_id": str(v.poet_id),
                    "poem_id": str(v.poem_id),
                    "is_famous": v.is_famous,
                    "view_count": v.view_count,
                } for v in rows]
                await vi.add_documents(docs, primary_key="id")
                indexed += len(docs)
                offset += chunk
                print(f"  Indexed {indexed} verses...", end="\r")

            print(f"  ✅ Indexed {indexed} verses        ")

            # ── Poets ──
            try:
                await client.delete_index("poets")
                await asyncio.sleep(1)
            except Exception:
                pass

            pi = await client.create_index("poets", primary_key="id")
            poets = (await session.execute(select(Poet))).scalars().all()
            poet_docs = [{
                "id": str(p.id),
                "name_ar": p.name_ar,
                "name_en": p.name_en or "",
                "slug": p.slug,
                "era": p.era or "",
                "bio_ar": (p.bio_ar or "")[:300],
                "poem_count": p.poem_count,
                "verse_count": p.verse_count,
            } for p in poets]
            await pi.add_documents(poet_docs)
            print(f"  ✅ Indexed {len(poet_docs)} poets")

    except Exception as e:
        print(f"  ⚠️  Meilisearch indexing failed: {e}")


# ── Verification ───────────────────────────────────────────────────────────────

async def verify(session: AsyncSession):
    poets_n  = (await session.execute(select(func.count()).select_from(Poet))).scalar()
    poems_n  = (await session.execute(select(func.count()).select_from(Poem))).scalar()
    verses_n = (await session.execute(select(func.count()).select_from(Verse))).scalar()
    cats_n   = (await session.execute(select(func.count()).select_from(Category))).scalar()

    print("\n" + "=" * 55)
    print("  ✅  SEEDING COMPLETE")
    print("=" * 55)
    print(f"  Poets:      {poets_n:>6,}")
    print(f"  Poems:      {poems_n:>6,}")
    print(f"  Verses:     {verses_n:>6,}")
    print(f"  Categories: {cats_n:>6,}")

    # Count by era
    era_rows = (await session.execute(
        select(Poet.era, func.count()).group_by(Poet.era).order_by(func.count().desc())
    )).all()
    print("\n  Poets by era:")
    for era, cnt in era_rows:
        print(f"    {era or 'unknown':<25} {cnt:>5}")

    # Poems per category
    cat_rows = (await session.execute(
        select(Category.name_ar, func.count(PoemCategory.poem_id))
        .join(PoemCategory, PoemCategory.category_id == Category.id, isouter=True)
        .group_by(Category.name_ar)
        .order_by(func.count(PoemCategory.poem_id).desc())
    )).all()
    print("\n  📂 Poems per category:")
    for name, cnt in cat_rows:
        if cnt:
            print(f"    {name:<25} {cnt:>5}")
    print("=" * 55)


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    print("🌱 Arabic Poetry Platform — Large Seed")
    print(f"   Faseeh poets : {len(FASEEH_POETS)}")
    print(f"   Nabati poets : {len(NABATI_POETS)}")
    print(f"   Total        : {len(ALL_POETS)}")

    async with engine.begin() as conn:
        for sql in [
            """DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS vector;
               EXCEPTION WHEN OTHERS THEN RAISE WARNING 'pgvector N/A'; END $$""",
            "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        ]:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass

    from app.core.database import Base
    import app.models  # noqa — registers all models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        cat_map = await seed_categories(session)
        await seed_all_poets(session, cat_map)
        await reindex_meilisearch(session)
        await verify(session)


if __name__ == "__main__":
    asyncio.run(main())
