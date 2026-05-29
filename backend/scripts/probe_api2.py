"""
Probe more API endpoints — poet-based poem lists.
"""
import asyncio
import httpx
import json

BASE = "https://api.qafiyah.com"


async def main():
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-research/1.0)"},
        timeout=20,
    ) as client:

        # Try poet-based endpoints
        poet_slug = "mihyar-al-daylami"
        endpoints = [
            f"{BASE}/poets/{poet_slug}",
            f"{BASE}/poets/{poet_slug}/poems",
            f"{BASE}/poet/{poet_slug}",
            f"{BASE}/poet/{poet_slug}/poems",
        ]
        for ep in endpoints:
            try:
                r = await client.get(ep)
                print(f"{ep} → {r.status_code}")
                if r.status_code == 200:
                    d = r.json()
                    print(f"  {json.dumps(d, ensure_ascii=False)[:400]}")
            except Exception as e:
                print(f"{ep} → ERROR: {e}")

        # Try search_type=poets
        print("\n\n--- search_type=poets ---")
        r = await client.get(f"{BASE}/search", params={
            "q": "مهيار", "search_type": "poets", "match_type": "any", "page": 1
        })
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            print(json.dumps(d, ensure_ascii=False, indent=2)[:800])

        # Try search_type=verses
        print("\n\n--- search_type=verses ---")
        r2 = await client.get(f"{BASE}/search", params={
            "q": "الشمس", "search_type": "verses", "match_type": "any", "page": 1
        })
        print(f"Status: {r2.status_code}")
        if r2.status_code == 200:
            d2 = r2.json()
            print(json.dumps(d2, ensure_ascii=False, indent=2)[:800])

        # How many pages does a big query return?
        print("\n\n--- Total pages for 'الشمس' ---")
        r3 = await client.get(f"{BASE}/search", params={
            "q": "الشمس", "search_type": "poems", "match_type": "any", "page": 1
        })
        if r3.status_code == 200:
            d3 = r3.json()
            pagination = d3.get("data", {}).get("pagination", {})
            print(f"  pagination: {pagination}")
            total = d3.get("data", {}).get("results", [{}])[0].get("total_count", "?")
            print(f"  total_count from first result: {total}")

        # Try fetching page 20, 30, 50 of a query
        for pg in [20, 30, 50, 100]:
            r4 = await client.get(f"{BASE}/search", params={
                "q": "الشمس", "search_type": "poems", "match_type": "any", "page": pg
            })
            if r4.status_code == 200:
                d4 = r4.json()
                results = d4.get("data", {}).get("results", [])
                print(f"  page {pg}: {len(results)} results")
            else:
                print(f"  page {pg}: status {r4.status_code}")


asyncio.run(main())
