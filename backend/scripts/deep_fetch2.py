"""
Deep Fetch — Pass 2.

Runs the most productive terms with max_pages=15 instead of 5,
plus new meter/rhyme/name terms not covered in pass 1.
Also saves to a SEPARATE cache (deep_cache2.json) so it's additive.

Run AFTER deep_fetch.py has completed:
    python -X utf8 scripts/deep_fetch2.py
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
CACHE2_FILE = os.path.join(os.path.dirname(__file__), "deep_cache2.json")
CACHE1_FILE = os.path.join(os.path.dirname(__file__), "deep_cache.json")

# ─────────────────────────────────────────────────────────────────────────────
# Extra terms not in Pass 1
# ─────────────────────────────────────────────────────────────────────────────

EXTRA_TERMS = [
    # ── Classical Arabic meters (بحور الشعر) ──────────────────────────────────
    "الطويل", "الكامل", "البسيط", "الوافر", "الرجز",
    "الخفيف", "الرمل", "السريع", "المتقارب", "المتدارك",
    "المجتث", "المديد", "المنسرح", "الهزج", "المقتضب",

    # ── Common rhyme letters (حروف القافية) ────────────────────────────────────
    # Words ending in common rhyme sounds
    "الليلا", "الحبيبا", "الغريبا",
    "الشبابا", "الترابا", "الحسابا",
    "المدينة", "الحزينة", "السفينة",
    "الأحلام", "الكلام", "الظلام",

    # ── More famous names / patrons in poetry ─────────────────────────────────
    "معاوية", "عمرو بن", "المتنبي", "البحتري", "أبو تمام",
    "الجاحظ", "الأصمعي", "الكسائي",

    # ── Specific famous poem first lines ──────────────────────────────────────
    "سلام على", "طال الثوى", "يا صاحبي", "خليليّ",
    "أقول لنفسي", "أيا من", "رحم الله",
    "هل غادر", "وقفت على", "سرت النفس",

    # ── More historical events / themes ───────────────────────────────────────
    "الأندلس", "صقلية", "الصليبيون", "المغول", "الفتوحات",
    "الخلافة", "الأمير", "الوزير", "الحاكم", "السلطان",

    # ── More emotions ──────────────────────────────────────────────────────────
    "الغضب", "الحقد", "الحسد", "الخوف", "الأمل",
    "اليأس", "الرجاء", "التوسل", "الشكوى",

    # ── More body/soul imagery ─────────────────────────────────────────────────
    "الجسد", "القبر", "الجنازة", "الروح", "البدن",
    "العقل", "القلب", "الفكر", "الخيال",

    # ── Seasons / time markers ────────────────────────────────────────────────
    "الغروب", "الشروق", "المغيب", "الأصيل",
    "البارحة", "الغداة", "السحر",

    # ── More food/drink imagery (used in descriptive poetry) ──────────────────
    "العسل", "اللبن", "التمر", "الزيتون",

    # ── Historical cities ─────────────────────────────────────────────────────
    "المدائن", "نيسابور", "سمرقند", "خراسان",
    "الإسكندرية", "قرطبة", "غرناطة", "إشبيلية",

    # ── Common Arabic verbs (stem forms that appear in poetry) ────────────────
    "يقول", "يبكي", "يعشق", "يكتب", "يرحل",
    "يبني", "يهدم", "ينتظر", "يحلم",

    # ── More tribal / Bedouin imagery ─────────────────────────────────────────
    "الخباء", "الخيمة", "الحمد", "البعير", "الناقة",
    "الخيل", "الصيد", "القنص",

    # ── Sufi themes ───────────────────────────────────────────────────────────
    "المريد", "الشيخ", "الطريقة", "الحقيقة", "الفناء",
    "البقاء", "العارف", "الولي", "الكشف",

    # ── Additional classical descriptive subjects ──────────────────────────────
    "الخمر", "الكأس", "الحان", "الساقي",
    "الربابة", "العود", "الناي", "المزمار",

    # ── More Nabati-adjacent terms ────────────────────────────────────────────
    "البادية", "الصحراء", "الإبل", "الرعي",

    # ── Random Arabic roots often appearing in poem titles ────────────────────
    "الإحسان", "البيان", "العيان", "الوجدان",
    "الإنسان", "الريحان", "الجنان",
]

# ── Re-run top 50 pass-1 terms with extended pages ───────────────────────────
TOP_PASS1_TERMS = [
    # These yielded 20-25 new poems in pass 1 at 5 pages → try 15 pages
    "الشمس", "القمر", "النجوم", "الليل", "الصبح", "الفجر",
    "المساء", "المطر", "البحر", "الجبل", "الماء", "الشجر",
    "الروض", "الطير", "القلب", "الروح", "الحب", "الهوى",
    "العشق", "الفراق", "الشوق", "الأيام", "الزمان", "الدهر",
    "السيف", "الخيل", "الحرب", "الفخر", "الدنيا", "الصمت",
    "القصيد", "الأبيات", "الغيرة", "الطلل", "الحنين",
    "الغيم", "الورد", "الزهر", "النبت", "البستان",
    "الرمل", "الريح", "سعاد", "ليلى", "لبنى",
    "بغداد", "دمشق", "الأندلس", "الكريم", "الجميل",
]

# Deduplicate
seen = set()
ALL_TERMS = []
for t in TOP_PASS1_TERMS + EXTRA_TERMS:
    if t not in seen:
        seen.add(t)
        ALL_TERMS.append(t)


async def fetch_poems_for_term(
    client: httpx.AsyncClient,
    term: str,
    max_pages: int,
) -> list[dict]:
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
            await asyncio.sleep(0.2)
        except Exception:
            break
    return results


async def deep_fetch2(all_existing: set[str]) -> dict:
    """
    all_existing: set of poem_slugs already in deep_cache.json
    Returns new poem_slug → poem_data dict.
    """
    print(f"\n🌐 Deep Fetch Pass 2: {len(ALL_TERMS)} terms")
    print(f"   Existing poems (pass 1): {len(all_existing)}")

    new_poems: dict[str, dict] = {}
    completed_terms: set[str] = set()

    # Load existing pass-2 cache if resuming
    if os.path.exists(CACHE2_FILE):
        try:
            with open(CACHE2_FILE, encoding="utf-8") as f:
                c = json.load(f)
            new_poems = c.get("poems", {})
            completed_terms = set(c.get("completed_terms", []))
            print(f"  Resuming: {len(new_poems)} new poems, {len(completed_terms)} terms done")
        except Exception:
            pass

    remaining = [t for t in ALL_TERMS if t not in completed_terms]
    print(f"  Remaining: {len(remaining)} terms\n")

    limits = httpx.Limits(max_connections=3, max_keepalive_connections=2)
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-bot/2.1)"},
        limits=limits,
    ) as client:
        for i, term in enumerate(remaining, 1):
            # Top terms get 15 pages, new terms get 8 pages
            max_p = 15 if term in set(TOP_PASS1_TERMS) else 8
            results = await fetch_poems_for_term(client, term, max_p)

            added = 0
            for poem in results:
                slug = poem.get("poem_slug", "")
                if slug and slug not in all_existing and slug not in new_poems:
                    new_poems[slug] = poem
                    added += 1

            completed_terms.add(term)
            total = len(new_poems)
            print(
                f"  [{i:>3}/{len(remaining)}] {term[:22]:<22} +{added:>4}  new_total={total:>5}",
                flush=True,
            )

            if i % 15 == 0:
                _save_cache(new_poems, completed_terms)
                print(f"  💾 Checkpoint ({total} new poems)")

            await asyncio.sleep(0.5)

    _save_cache(new_poems, completed_terms)
    print(f"\n  ✅ Pass 2 collected {len(new_poems)} additional unique poems")
    return new_poems


def _save_cache(poems: dict, completed_terms: set):
    with open(CACHE2_FILE, "w", encoding="utf-8") as f:
        json.dump({"poems": poems, "completed_terms": list(completed_terms)},
                  f, ensure_ascii=False)


# ── Import (reuses deep_fetch.py's import logic) ─────────────────────────────
from scripts.deep_fetch import import_poems, reindex_meilisearch, verify  # noqa

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models import Category

db_engine = create_async_engine(settings.database_url, echo=False)
DbSession = async_sessionmaker(db_engine, expire_on_commit=False)


async def main():
    t0 = time.time()

    # Load pass-1 existing slugs
    existing_slugs: set[str] = set()
    if os.path.exists(CACHE1_FILE):
        with open(CACHE1_FILE, encoding="utf-8") as f:
            existing_slugs = set(json.load(f).get("poems", {}).keys())
        print(f"Pass-1 cache has {len(existing_slugs)} poems")

    new_poems = await deep_fetch2(existing_slugs)

    print("\n🗄️  Importing pass-2 poems into DB...")
    async with DbSession() as session:
        cat_rows = (await session.execute(select(Category))).scalars().all()
        cat_map = {c.slug: c for c in cat_rows}

        new_poets, new_poem_count = await import_poems(session, new_poems, cat_map)
        print(f"  ✅ Added {new_poets} poets, {new_poem_count} poems")

        await reindex_meilisearch(session)
        await verify(session)

    print(f"\n  Total time: {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    asyncio.run(main())
