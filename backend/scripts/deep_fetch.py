"""
Deep poem harvester — 300+ search terms × 5 pages each.

Strategy:
- Search poems (not poets) using hundreds of common Arabic words
- Paginate up to 5 pages per term
- Deduplicate by poem_slug
- Import into DB — UPDATES existing poets with new poems too

Run:
    python -X utf8 scripts/deep_fetch.py

Takes ~30-60 min for the full run; uses rate-limited async HTTP.
Progress is saved to deep_cache.json so it can be resumed.
"""

import asyncio
import sys
import os
import json
import re
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE = "https://api.qafiyah.com"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "deep_cache.json")

# ─────────────────────────────────────────────────────────────────────────────
# 300+ search terms — broad Arabic words found in classical poetry
# ─────────────────────────────────────────────────────────────────────────────

SEARCH_TERMS = [
    # Common nouns — nature
    "الشمس", "القمر", "النجوم", "الليل", "الصبح", "الفجر", "المساء",
    "الريح", "المطر", "البحر", "النهر", "الجبل", "الصحراء", "الغيم",
    "الورد", "الزهر", "النبت", "الماء", "الشجر", "الروض", "البستان",
    "الطير", "الحمام", "العصفور", "الغزال", "الظبي", "الأسد",
    # Common nouns — human
    "القلب", "الروح", "العين", "الوجه", "اليد", "الشعر",
    "الدم", "الدمع", "البكاء", "الضحك", "الجمال", "الحسن",
    # Emotions / concepts
    "الحب", "الهوى", "العشق", "الغرام", "الوجد", "الشوق",
    "الفراق", "الهجر", "الوصال", "الحنين", "الوجع", "الألم",
    "الحزن", "الفرح", "السعادة", "الأمل", "الحلم", "الوهم",
    # Time
    "الأيام", "الزمان", "الدهر", "الليالي", "السنين", "الأزمان",
    "الأمس", "اليوم", "الغد", "الآن",
    # War / valor
    "السيف", "الرمح", "الخيل", "الحرب", "الفخر", "الشجاعة",
    "البطل", "الجهاد", "النصر", "الظفر", "الفتح",
    # Religion / zuhd
    "الإيمان", "الدنيا", "الآخرة", "الجنة", "النار", "التقوى",
    "الزهد", "الصبر", "التوبة", "الدعاء", "الحمد",
    # Places
    "بغداد", "دمشق", "القاهرة", "مكة", "المدينة", "الأندلس",
    "الشام", "العراق", "مصر", "الحجاز", "اليمن", "المغرب",
    "الفرات", "دجلة", "النيل",
    # Famous female names (subjects of ghazal)
    "سعاد", "ليلى", "لبنى", "عبلة", "هند", "زينب", "سلمى",
    "رباب", "دعد", "مية", "نوار", "أسماء",
    # Praise / panegyric themes
    "المدح", "الكرم", "الجود", "السخاء", "الشرف", "المجد",
    "العلا", "المنزلة", "الرفعة",
    # Elegy themes
    "الرثاء", "الفقد", "المصيبة", "الفاجعة", "المأتم",
    # Common verb forms (past)
    "قالت", "قلت", "جاء", "ذهب", "رأيت", "سألت", "أجاب",
    "عاش", "مات", "رحل", "غاب", "بكيت", "ضحكت",
    # Common poetic openers / exclamations
    "يا ليل", "يا دار", "يا عين", "يا قلب", "يا نفس",
    "ألا يا", "هل تذكر", "أما زلت", "إذا ما", "كم من",
    "قفا نبك", "بانت سعاد", "ألا ليت", "لمن الديار",
    # Geometric / abstract
    "النور", "الظلام", "الأثر", "الذكر", "الصمت",
    "الصوت", "الكلام", "الشعر", "القصيد", "الأبيات",
    # Common Nabati/popular themes
    "الغيرة", "الغيرة", "الفزعة", "العرب", "القبيلة",
    # Additional classical themes
    "الطلل", "الأطلال", "الديار", "المنازل", "الرحلة",
    "الهجرة", "الغربة", "الوطن", "الأهل", "الأحباب",
    # Weather / season
    "الربيع", "الصيف", "الخريف", "الشتاء", "البرد", "الحر",
    # Body metaphors in poetry
    "الثغر", "الخد", "الصدغ", "القد", "الخصر",
    # Stars / constellations
    "النجم", "الكوكب", "الثريا", "الجوزاء", "الهلال", "البدر",
    # Common verbs (present)
    "أحب", "أهوى", "أبكي", "أرجو", "أخشى", "أظن",
    "يمشي", "يجري", "يطير", "يغني", "يبكي",
    # Metals / gems (used in description)
    "الذهب", "الفضة", "اللؤلؤ", "الياقوت", "الدر",
    # Animals used as metaphor
    "الحمامة", "الحمام", "النسر", "الصقر", "الثعلب",
    # Common adjectives
    "الجميل", "الحسناء", "الكريم", "الشريف", "النبيل",
    "المجنون", "العاقل", "الغيور", "الصبور", "الجريء",
    # Verbs in imperative
    "اسمع", "انظر", "تذكر", "افكر", "اصبر", "ابكِ",
    # Common expressions
    "لا تحزن", "كن صبورا", "يا رب", "سبحان الله",
    # Historical figures (subjects of poems)
    "الرسول", "النبي", "علي", "الحسين", "عمر", "عثمان",
    # Love / longing themes
    "العاشق", "المعشوق", "الحبيب", "الغائب", "المسافر",
    # Death / eternity
    "الموت", "الفناء", "البقاء", "الأبد", "الخلود",
    # Travel / journey
    "السفر", "الطريق", "المسير", "الرحيل", "الوداع",
    # Food / drink (used in description & wine poetry)
    "الخمر", "الكأس", "الشراب", "النبيذ",
    # Cities / rivers
    "الكوفة", "البصرة", "الأنبار", "واسط", "الموصل",
    "الرقة", "حلب", "حمص", "طرابلس", "القيروان",
    # Fame / legacy
    "الشهرة", "الذكر", "التاريخ", "المجد", "الأثر",
    # More first-line fragments
    "ولما رأيت", "وكم قد رأيت", "أقول وقد", "ألا قاتل الله",
    "وما كنت", "فلا تيأس", "إذا كنت", "من لي بمثل",
    "يا من رأى", "سقى الله", "حياك الله", "رعاك الله",
]

# Remove duplicates while preserving order
seen = set()
SEARCH_TERMS = [t for t in SEARCH_TERMS if not (t in seen or seen.add(t))]


# ─────────────────────────────────────────────────────────────────────────────
# Fetch phase
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_poems_for_term(
    client: httpx.AsyncClient,
    term: str,
    max_pages: int = 5,
) -> list[dict]:
    """Search poems for a single term, paginate up to max_pages."""
    results = []
    for page in range(1, max_pages + 1):
        try:
            r = await client.get(
                f"{BASE}/search",
                params={"q": term, "search_type": "poems", "match_type": "any", "page": page},
                timeout=25,
            )
            if r.status_code != 200:
                break
            data = r.json()["data"]
            page_results = data.get("results", [])
            if not page_results:
                break
            results.extend(page_results)
            if not data["pagination"]["hasNextPage"]:
                break
            await asyncio.sleep(0.25)
        except Exception as e:
            break  # skip on error
    return results


async def deep_fetch() -> dict:
    """
    Fire all search terms, collect all unique poems.
    Returns { poem_slug → poem_data }
    """
    print(f"\n🌐 Deep fetching {len(SEARCH_TERMS)} search terms × up to 5 pages each...")
    print("   This collects all unique poems from the API.\n")

    # Load existing cache if partial
    all_poems: dict[str, dict] = {}
    completed_terms: set[str] = set()

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                cache = json.load(f)
            all_poems = cache.get("poems", {})
            completed_terms = set(cache.get("completed_terms", []))
            print(f"  📂 Resuming from cache: {len(all_poems)} poems, {len(completed_terms)} terms done")
        except Exception:
            pass

    remaining = [t for t in SEARCH_TERMS if t not in completed_terms]
    print(f"  Remaining terms: {len(remaining)}")

    limits = httpx.Limits(max_connections=3, max_keepalive_connections=2)
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-bot/2.0)"},
        limits=limits,
    ) as client:
        for i, term in enumerate(remaining, 1):
            results = await fetch_poems_for_term(client, term)
            new_count = 0
            for poem in results:
                slug = poem.get("poem_slug", "")
                if slug and slug not in all_poems:
                    all_poems[slug] = poem
                    new_count += 1

            completed_terms.add(term)
            total = len(all_poems)
            print(
                f"  [{i:>3}/{len(remaining)}] {term[:20]:<20} +{new_count:>4} new  total={total:>6}",
                flush=True,
            )

            # Save checkpoint every 20 terms
            if i % 20 == 0:
                _save_cache(all_poems, completed_terms)
                print(f"  💾 Checkpoint saved ({total} poems)")

            await asyncio.sleep(0.4)

    _save_cache(all_poems, completed_terms)
    print(f"\n  ✅ Collected {len(all_poems)} unique poems from API")
    return all_poems


def _save_cache(poems: dict, completed_terms: set):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"poems": poems, "completed_terms": list(completed_terms)},
            f,
            ensure_ascii=False,
            indent=None,  # compact
        )


# ─────────────────────────────────────────────────────────────────────────────
# Import phase
# ─────────────────────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, text, func
from app.core.config import settings
from app.models import Poet, Poem, Verse, Category, PoemCategory
from app.utils.arabic_normalizer import normalizer, arabic_to_slug as _slug

db_engine = create_async_engine(settings.database_url, echo=False)
DbSession = async_sessionmaker(db_engine, expire_on_commit=False)

ERA_MAP = {
    "جاهلي": "pre_islamic", "مخضرم": "islamic", "إسلامي": "islamic",
    "أموي": "umayyad", "عباسي": "abbasid", "أندلسي": "andalusian",
    "أيوبي": "abbasid", "مملوكي": "abbasid", "عثماني": "modern", "متأخر": "modern",
}

METER_MAP = {
    "الطويل": "الطويل", "الكامل": "الكامل", "البسيط": "البسيط",
    "الوافر": "الوافر", "الرجز": "الرجز", "الخفيف": "الخفيف",
    "الرمل": "الرمل", "السريع": "السريع", "المتقارب": "المتقارب",
    "المتدارك": "المتدارك", "المجتث": "المجتث", "المديد": "المديد",
    "المنسرح": "المنسرح", "الهزج": "الهزج",
}


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


def map_era(era_ar: str) -> str:
    for ar, slug in ERA_MAP.items():
        if ar in era_ar:
            return slug
    return "abbasid"


def map_categories_for_era(era_ar: str) -> list[str]:
    if "جاهلي" in era_ar or "مخضرم" in era_ar:
        return ["pride", "description"]
    elif "أموي" in era_ar:
        return ["love", "pride"]
    elif "عباسي" in era_ar or "أيوبي" in era_ar or "مملوكي" in era_ar:
        return ["praise", "wisdom"]
    elif "أندلسي" in era_ar:
        return ["love", "description"]
    elif "عثماني" in era_ar or "متأخر" in era_ar:
        return ["wisdom", "elegy"]
    return ["wisdom"]


async def unique_poem_slug(session: AsyncSession, slug: str) -> str:
    n = 2
    base = slug[:550]
    while True:
        r = await session.execute(select(Poem.id).where(Poem.slug == slug))
        if r.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


async def import_poems(session: AsyncSession, all_poems: dict, cat_map: dict) -> tuple[int, int]:
    """
    Import all poems into DB.
    - Creates poet if not exists
    - Adds poem if poem_slug not already in DB (tracks by source metadata)
    Returns (poets_added, poems_added).
    """
    # Track which poem qafiyah slugs we've already imported
    existing_qafiyah_slugs: set[str] = set()
    rows = (await session.execute(
        select(Poem.metadata_).where(Poem.metadata_.isnot(None))
    )).scalars().all()
    for meta in rows:
        if isinstance(meta, dict) and "qafiyah_slug" in meta:
            existing_qafiyah_slugs.add(meta["qafiyah_slug"])

    print(f"  Already imported: {len(existing_qafiyah_slugs)} poems (by qafiyah slug)")

    # Get all existing poets (slug → id)
    poet_rows = (await session.execute(select(Poet.slug, Poet.id, Poet.era))).all()
    poet_map: dict[str, tuple] = {r[0]: (r[1], r[2]) for r in poet_rows}

    # Group poems by poet_slug
    by_poet: dict[str, list[dict]] = {}
    for poem_slug, poem in all_poems.items():
        poet_slug = poem.get("poet_slug", "")
        if not poet_slug:
            continue
        if poem_slug in existing_qafiyah_slugs:
            continue  # already imported
        by_poet.setdefault(poet_slug, []).append(poem)

    print(f"  New poems to import: {sum(len(v) for v in by_poet.values())} across {len(by_poet)} poets")

    poets_created = 0
    poems_added = 0
    verses_added = 0

    poet_slugs = list(by_poet.keys())
    BATCH = 40

    for b_start in range(0, len(poet_slugs), BATCH):
        batch = poet_slugs[b_start:b_start + BATCH]

        for poet_slug in batch:
            poems_for_poet = by_poet[poet_slug]

            # Ensure poet exists
            if poet_slug not in poet_map:
                # Create poet from first poem's data
                sample = poems_for_poet[0]
                era_ar = sample.get("poet_era", "")
                era = map_era(era_ar)
                name_ar = sample.get("poet_name", "")
                if not name_ar:
                    continue

                poet = Poet(
                    name_ar=name_ar,
                    slug=poet_slug,
                    bio_ar=f"شاعر عربي من العصر {era_ar}",
                    era=era,
                    nationality_ar="عربي",
                    is_verified=True,
                    metadata_={"source": "qafiyah.com"},
                )
                session.add(poet)
                await session.flush()
                poet_id = poet.id
                poet_map[poet_slug] = (poet_id, era)
                poets_created += 1
            else:
                poet_id, _ = poet_map[poet_slug]

            # Import poems for this poet
            for poem_data in poems_for_poet[:50]:  # max 50 poems per poet per run
                qafiyah_slug = poem_data.get("poem_slug", "")
                title_ar = poem_data.get("poem_title", "")
                snippet = poem_data.get("poem_snippet", "")
                meter_ar = poem_data.get("poem_meter", "")
                era_ar = poem_data.get("poet_era", "")
                poet_name = poem_data.get("poet_name", "")

                if not title_ar or not snippet:
                    continue

                verses = parse_snippet(snippet)
                if not verses:
                    continue

                full_text = "\n".join(
                    f"{h1} *** {h2}" if h2 else h1
                    for h1, h2 in verses
                )

                # Generate slug
                base = _slug(title_ar) or "poem"
                poem_slug_db = await unique_poem_slug(
                    session, f"{poet_slug}-{base}"[:560]
                )

                era = map_era(era_ar)
                poem = Poem(
                    poet_id=poet_id,
                    title_ar=title_ar,
                    slug=poem_slug_db,
                    full_text=full_text,
                    meter=METER_MAP.get(meter_ar, None),
                    verse_count=len(verses),
                    era=era,
                    is_verified=True,
                    is_published=True,
                    source="qafiyah.com",
                    metadata_={"qafiyah_slug": qafiyah_slug},
                )
                session.add(poem)
                await session.flush()

                # Categories
                for cat_slug in map_categories_for_era(era_ar):
                    if cat_slug in cat_map:
                        session.add(PoemCategory(poem_id=poem.id, category_id=cat_map[cat_slug].id))

                # Verses
                for pos, (h1, h2) in enumerate(verses, 1):
                    full_verse = f"{h1} *** {h2}" if h2 else h1
                    session.add(Verse(
                        poem_id=poem.id,
                        poet_id=poet_id,
                        position=pos,
                        hemistich_1=h1,
                        hemistich_2=h2 or None,
                        full_verse=full_verse,
                        full_verse_normalized=normalizer.normalize(full_verse),
                        hemistich_1_normalized=normalizer.normalize(h1),
                        hemistich_2_normalized=normalizer.normalize(h2) if h2 else None,
                        poet_name_ar=poet_name,
                        poet_slug=poet_slug,
                        poem_title_ar=title_ar,
                        poem_slug=poem_slug_db,
                        is_famous=False,
                    ))
                    verses_added += 1

                existing_qafiyah_slugs.add(qafiyah_slug)
                poems_added += 1

        await session.commit()
        print(
            f"  Batch {b_start // BATCH + 1:>2}: "
            f"{poets_created} new poets, {poems_added} poems, {verses_added} verses"
        )

    # Update poem_count / verse_count on all poets
    print("  Updating poet statistics...")
    poet_stats = (await session.execute(
        select(Verse.poet_id, func.count(Verse.id).label("vc"),
               func.count(Verse.poem_id.distinct()).label("pc"))
        .group_by(Verse.poet_id)
    )).all()
    for poet_id, vc, pc in poet_stats:
        await session.execute(
            text("UPDATE poets SET verse_count=:vc, poem_count=:pc WHERE id=:id"),
            {"vc": vc, "pc": pc, "id": str(poet_id)},
        )
    await session.commit()

    return poets_created, poems_added


async def reindex_meilisearch(session: AsyncSession):
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
                "full_verse", "full_verse_normalized",
                "hemistich_1", "hemistich_2",
                "hemistich_1_normalized", "hemistich_2_normalized",
                "poet_name_ar", "poem_title_ar",
            ])
            await vi.update_filterable_attributes(["poet_id", "poem_id", "is_famous", "poet_slug"])
            await vi.update_sortable_attributes(["view_count"])

            offset, total = 0, 0
            while True:
                rows = (await session.execute(select(Verse).offset(offset).limit(500))).scalars().all()
                if not rows:
                    break
                await vi.add_documents([{
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
                } for v in rows], primary_key="id")
                total += len(rows)
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
                "slug": p.slug, "era": p.era or "",
                "bio_ar": (p.bio_ar or "")[:300],
                "poem_count": p.poem_count, "verse_count": p.verse_count,
            } for p in poets])
            print(f"  ✅ Indexed {len(poets)} poets")

    except Exception as e:
        print(f"  ⚠️  Meilisearch failed: {e}")


async def verify(session: AsyncSession):
    p  = (await session.execute(select(func.count()).select_from(Poet))).scalar()
    po = (await session.execute(select(func.count()).select_from(Poem))).scalar()
    v  = (await session.execute(select(func.count()).select_from(Verse))).scalar()
    print("\n" + "=" * 55)
    print("  ✅  DEEP FETCH COMPLETE")
    print("=" * 55)
    print(f"  Poets:   {p:>7,}")
    print(f"  Poems:   {po:>7,}")
    print(f"  Verses:  {v:>7,}")

    era_rows = (await session.execute(
        select(Poet.era, func.count()).group_by(Poet.era).order_by(func.count().desc())
    )).all()
    print("\n  Poets by era:")
    for era, cnt in era_rows:
        print(f"    {era or 'unknown':<25} {cnt:>5}")
    print("=" * 55)


async def main():
    t0 = time.time()

    # Phase 1 — Fetch
    all_poems = await deep_fetch()

    # Phase 2 — Import
    print("\n🗄️  Phase 2: Importing into poetry_db...")
    async with DbSession() as session:
        cat_rows = (await session.execute(select(Category))).scalars().all()
        cat_map = {c.slug: c for c in cat_rows}
        print(f"  Categories: {len(cat_map)}")

        new_poets, new_poems = await import_poems(session, all_poems, cat_map)
        print(f"\n  ✅ Added {new_poets} new poets, {new_poems} new poems")

        await reindex_meilisearch(session)
        await verify(session)

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed/60:.1f} min")


if __name__ == "__main__":
    asyncio.run(main())
