"""
Deep Fetch — Pass 3.

Focuses on the highest-yield search terms with up to 200 pages each
(vs 15 pages in pass 2). Saves to deep_cache3.json (additive).

Run from backend root:
    python -X utf8 scripts/deep_fetch3.py
"""

import asyncio
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE = "https://api.qafiyah.com"
CACHE3_FILE = os.path.join(os.path.dirname(__file__), "deep_cache3.json")
CACHE1_FILE = os.path.join(os.path.dirname(__file__), "deep_cache.json")
CACHE2_FILE = os.path.join(os.path.dirname(__file__), "deep_cache2.json")

# High-yield terms sorted by total_results (from probe_yield.py)
# We cap each at 200 pages — enough to get 1,000 poems per term
TOP_TERMS = [
    ("الله",    200),
    ("الزمان",  200),
    ("القلب",   200),
    ("الليل",   200),
    ("الشمس",   200),
    ("الحب",    200),
    ("العين",   200),
    ("الموت",   150),
    ("الماء",   150),
    ("الشعر",   100),
    ("الحرب",   100),
    ("السيف",   100),
    ("الحياة",  100),
    ("البحر",   100),
    ("الصبر",   100),
    ("الشوق",   80),
    ("النجوم",  80),
    ("النار",   80),
    ("الخيل",   80),
    ("الورد",   60),
    ("الريح",   60),
    ("الفراق",  60),
    ("الدموع",  60),
    ("الإسلام", 60),
    ("الطير",   50),
    ("العقل",   50),
    ("الروح",   50),
    ("الفكر",   40),
    ("الفخر",   40),
    ("النصر",   40),
    ("القمر",   30),
    ("الأمل",   20),
]


async def fetch_poems_for_term(
    client: httpx.AsyncClient,
    term: str,
    max_pages: int,
    existing_slugs: set,
) -> list[dict]:
    """Fetch up to max_pages for term, return poems NOT already in existing_slugs."""
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

            for poem in page_results:
                slug = poem.get("poem_slug", "")
                if slug and slug not in existing_slugs:
                    results.append(poem)

            pagination = data.get("pagination", {})
            if not pagination.get("hasNextPage"):
                break

            # Polite delay
            await asyncio.sleep(0.25)

        except httpx.TimeoutException:
            await asyncio.sleep(2)
            continue
        except Exception as e:
            print(f"    Error page {page}: {e}")
            break

    return results


async def deep_fetch3(all_existing: set[str]) -> dict:
    print(f"\n🌐 Deep Fetch Pass 3: {len(TOP_TERMS)} terms, up to 200 pages each")
    print(f"   Existing poems (passes 1+2): {len(all_existing)}")

    new_poems: dict[str, dict] = {}
    completed_terms: list[str] = []

    # Resume from checkpoint
    if os.path.exists(CACHE3_FILE):
        try:
            with open(CACHE3_FILE, encoding="utf-8") as f:
                c = json.load(f)
            new_poems = c.get("poems", {})
            completed_terms = c.get("completed_terms", [])
            print(f"  Resuming: {len(new_poems)} new poems, {len(completed_terms)} terms done")
        except Exception:
            pass

    completed_set = set(completed_terms)
    remaining = [(t, p) for t, p in TOP_TERMS if t not in completed_set]
    print(f"  Remaining: {len(remaining)} terms\n")

    # Build full existing set (pass 1+2 + any already added in pass 3)
    all_seen = all_existing | set(new_poems.keys())

    limits = httpx.Limits(max_connections=3, max_keepalive_connections=2)
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-bot/3.0)"},
        limits=limits,
    ) as client:
        for i, (term, max_p) in enumerate(remaining, 1):
            t0 = time.time()
            results = await fetch_poems_for_term(client, term, max_p, all_seen)

            added = 0
            for poem in results:
                slug = poem.get("poem_slug", "")
                if slug and slug not in all_seen:
                    new_poems[slug] = poem
                    all_seen.add(slug)
                    added += 1

            completed_terms.append(term)
            elapsed = time.time() - t0
            total = len(new_poems)
            print(
                f"  [{i:>2}/{len(remaining)}] {term:<12} "
                f"+{added:>5} poems  total={total:>6,}  ({elapsed:.0f}s)",
                flush=True,
            )

            # Checkpoint every 5 terms
            if i % 5 == 0:
                _save_cache(new_poems, completed_terms)
                print(f"  💾 Checkpoint saved ({total:,} new poems)")

            await asyncio.sleep(0.5)

    _save_cache(new_poems, completed_terms)
    print(f"\n  ✅ Pass 3 collected {len(new_poems):,} additional unique poems")
    return new_poems


def _save_cache(poems: dict, completed_terms: list):
    with open(CACHE3_FILE, "w", encoding="utf-8") as f:
        json.dump({"poems": poems, "completed_terms": completed_terms},
                  f, ensure_ascii=False)


# ── Reuse import/index/verify from deep_fetch.py ─────────────────────────────
from scripts.deep_fetch import import_poems, reindex_meilisearch, verify  # noqa

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models import Category

db_engine = create_async_engine(settings.database_url, echo=False)
DbSession = async_sessionmaker(db_engine, expire_on_commit=False)


async def main():
    t0 = time.time()
    print("🌱 Arabic Poetry Platform — Deep Fetch Pass 3")

    # Load all existing slugs from passes 1 and 2
    existing_slugs: set[str] = set()
    for cache_file in [CACHE1_FILE, CACHE2_FILE]:
        if os.path.exists(cache_file):
            with open(cache_file, encoding="utf-8") as f:
                d = json.load(f)
            slugs = set(d.get("poems", {}).keys())
            existing_slugs |= slugs
            print(f"  Loaded {len(slugs):,} slugs from {os.path.basename(cache_file)}")

    print(f"  Total existing across passes 1+2: {len(existing_slugs):,}")

    new_poems = await deep_fetch3(existing_slugs)

    print(f"\n🗄️  Importing pass-3 poems into DB...")
    async with DbSession() as session:
        cat_rows = (await session.execute(select(Category))).scalars().all()
        cat_map = {c.slug: c for c in cat_rows}

        new_poets, new_poem_count = await import_poems(session, new_poems, cat_map)
        print(f"  ✅ Added {new_poets} poets, {new_poem_count} poems")

        await reindex_meilisearch(session)
        await verify(session)

    total_elapsed = time.time() - t0
    print(f"\n  Total time: {total_elapsed/60:.1f} min")


if __name__ == "__main__":
    asyncio.run(main())
