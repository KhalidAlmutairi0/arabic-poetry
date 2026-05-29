"""
Check total_count for top Arabic search terms to prioritize deep fetch pass 3.
"""
import asyncio
import httpx

BASE = "https://api.qafiyah.com"

TOP_TERMS = [
    "الشمس", "القمر", "الليل", "الحب", "الفراق",
    "الشوق", "الدموع", "الصبر", "الوطن", "الزمان",
    "البحر", "الشعر", "الموت", "الحياة", "القلب",
    "العين", "اليد", "الروح", "العقل", "الفكر",
    "السيف", "الخيل", "الحرب", "النصر", "الفخر",
    "الله", "الإسلام", "الصلاة", "الدعاء", "الأمل",
    "المطر", "الجبل", "الريح", "النار", "الماء",
    "الورد", "الطير", "النجوم", "الصحراء", "الخيمة",
]


async def get_total(client, term):
    try:
        r = await client.get(f"{BASE}/search", params={
            "q": term, "search_type": "poems", "match_type": "any", "page": 1
        }, timeout=15)
        if r.status_code == 200:
            d = r.json()
            pagination = d.get("data", {}).get("pagination", {})
            total_pages = pagination.get("totalPages", 0)
            total_results = pagination.get("totalResults", 0)
            return term, total_results, total_pages
    except Exception as e:
        pass
    return term, 0, 0


async def main():
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-research/1.0)"},
        limits=httpx.Limits(max_connections=5),
    ) as client:
        tasks = [get_total(client, t) for t in TOP_TERMS]
        results = await asyncio.gather(*tasks)

    results_sorted = sorted(results, key=lambda x: x[1], reverse=True)
    print(f"{'Term':<15} {'Results':>8} {'Pages':>6}")
    print("-" * 32)
    total_unique = 0
    for term, total, pages in results_sorted:
        print(f"{term:<15} {total:>8,} {pages:>6}")
        total_unique += total

    print(f"\nTotal across all terms: {total_unique:,} (with overlap)")
    print(f"Approx unique at 60% dedup: {int(total_unique * 0.4):,}")


asyncio.run(main())
