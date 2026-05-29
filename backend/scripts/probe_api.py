"""
Probe qafiyah.com API to find full-poem endpoints.
Run from backend root:
    python -X utf8 scripts/probe_api.py
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

        # 1. Search for one poem to get its slug/id
        r = await client.get(f"{BASE}/search", params={
            "q": "قفا نبك", "search_type": "poems", "match_type": "any", "page": 1
        })
        print(f"Search status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            results = data.get("data", {}).get("results", [])
            if results:
                first = results[0]
                print(f"\nFirst result keys: {list(first.keys())}")
                print(f"First result: {json.dumps(first, ensure_ascii=False, indent=2)[:500]}")

                slug = first.get("poem_slug", "")
                poet_slug = first.get("poet_slug", "")
                poem_id = first.get("poem_id", first.get("id", ""))
                print(f"\nslug={slug!r}  poet_slug={poet_slug!r}  poem_id={poem_id!r}")

                # Try various detail endpoints
                endpoints = [
                    f"{BASE}/poems/{slug}",
                    f"{BASE}/poem/{slug}",
                    f"{BASE}/poems/{poem_id}",
                    f"{BASE}/poem/{poem_id}",
                    f"{BASE}/poets/{poet_slug}/poems/{slug}",
                    f"{BASE}/search?q={slug}&search_type=poems&match_type=any&page=1",
                ]
                for ep in endpoints:
                    try:
                        r2 = await client.get(ep)
                        print(f"\n  {ep}")
                        print(f"  Status: {r2.status_code}")
                        if r2.status_code == 200:
                            d = r2.json()
                            print(f"  Keys: {list(d.keys()) if isinstance(d, dict) else 'list'}")
                            print(f"  Preview: {json.dumps(d, ensure_ascii=False)[:300]}")
                    except Exception as e:
                        print(f"  {ep} → ERROR: {e}")

        # 2. Try root / docs endpoints
        for ep in [f"{BASE}/", f"{BASE}/docs", f"{BASE}/poets", f"{BASE}/poems"]:
            try:
                r3 = await client.get(ep, timeout=8)
                print(f"\n{ep} → {r3.status_code}")
                if r3.status_code == 200:
                    d = r3.json()
                    print(f"  {json.dumps(d, ensure_ascii=False)[:200]}")
            except Exception as e:
                print(f"{ep} → {e}")


asyncio.run(main())
