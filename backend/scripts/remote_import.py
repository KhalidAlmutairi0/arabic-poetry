"""
Remote bulk import — fetches from HuggingFace locally and POSTs poems
directly to the Render backend's import endpoint.

Bypasses Render's slow HuggingFace connection by doing the fetch locally.

Usage: python scripts/remote_import.py
"""

import json
import urllib.request
import time
import sys
import re

BACKEND_URL = "https://poetry-backend-36qe.onrender.com"
SECRET_KEY = "Tl7HOWa0VksqG1bLro3b7NQdmlvQZWweeQER9pqczPw="
HF_API = "https://datasets-server.huggingface.co/rows"
DATASET = "arbml/Ashaar_dataset"
BATCH_SIZE = 100  # rows per HF request
IMPORT_BATCH = 50  # poems per POST to backend

METER_NAMES = [
    "البسيط", "الخفيف", "الرجز", "الرمل", "السريع", "الطويل", "الكامل",
    "المتدارك", "المتقارب", "المجتث", "المديد", "المضارع", "المقتضب",
    "المنسرح", "النثر", "الهزج", "الوافر",
]

ERA_MAP = {
    "العصر الجاهلي": "pre_islamic", "الجاهلي": "pre_islamic",
    "صدر الإسلام": "islamic_early", "عصر صدر الإسلام": "islamic_early",
    "العصر الأموي": "umayyad", "الأموي": "umayyad",
    "العصر العباسي": "abbasid", "العباسي": "abbasid",
    "العصر الأندلسي": "andalusian",
    "العصر المملوكي": "mamluk", "العصر الأيوبي": "abbasid",
    "العصر العثماني": "ottoman",
    "العصر الحديث": "modern", "الحديث": "modern",
    "العصر المعاصر": "contemporary", "المعاصر": "contemporary",
}


def map_era(s):
    for ar, slug in ERA_MAP.items():
        if ar in (s or ""):
            return slug
    return "abbasid"


def make_slug(text):
    try:
        from unidecode import unidecode
        return re.sub(r"[^a-z0-9]+", "-", unidecode(text).lower()).strip("-")[:200] or "unknown"
    except Exception:
        return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:200] or "unknown"


def fetch_hf_rows(offset, length=100):
    url = f"{HF_API}?dataset=arbml%2FAshaar_dataset&config=default&split=train&offset={offset}&length={length}"
    try:
        data = json.loads(urllib.request.urlopen(url, timeout=30).read())
        return data.get("rows", [])
    except Exception as e:
        print(f"  HF fetch error at offset {offset}: {e}")
        return []


def parse_row(item):
    row = item.get("row", {})
    poet_name = (row.get("poet_name") or "").strip()
    title = (row.get("poem_title") or "").strip()
    verses_list = row.get("poem_verses") or []
    raw_meter = row.get("poem_meter")
    era = (row.get("poet_era") or "").strip()
    poet_bio = (row.get("poet_description") or "").strip()[:500]

    if isinstance(raw_meter, int) and 0 <= raw_meter < len(METER_NAMES):
        meter = METER_NAMES[raw_meter]
    elif isinstance(raw_meter, str) and raw_meter not in ("", "nan"):
        meter = raw_meter
    else:
        meter = None

    if not poet_name or not verses_list:
        return None

    verses = []
    for v in verses_list:
        if not v or not isinstance(v, str) or len(v.strip()) < 3:
            continue
        verses.append(v.strip())

    if not verses:
        return None
    if not title:
        title = verses[0][:60]

    poet_slug = make_slug(poet_name)
    poem_slug = f"{poet_slug}-{make_slug(title)}"[:580]

    return {
        "poet_name": poet_name,
        "poet_slug": poet_slug,
        "poet_bio": poet_bio,
        "era": map_era(era),
        "title": title,
        "poem_slug": poem_slug,
        "meter": meter,
        "verses": verses,
    }


def post_poems(poems):
    """POST a batch of poems to the backend seed-bulk endpoint."""
    url = f"{BACKEND_URL}/admin/seed-bulk?key={urllib.parse.quote(SECRET_KEY)}"
    payload = json.dumps(poems, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


import urllib.parse


def main():
    start_offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    max_offset = int(sys.argv[2]) if len(sys.argv) > 2 else 212500

    print(f"Importing from HuggingFace offset {start_offset} to {max_offset}")
    print(f"Backend: {BACKEND_URL}")
    print()

    total_poems = 0
    total_verses = 0
    total_posted = 0
    batch = []
    t0 = time.time()

    offset = start_offset
    while offset < max_offset:
        rows = fetch_hf_rows(offset, BATCH_SIZE)
        if not rows:
            print(f"  No more rows at offset {offset}")
            break

        for item in rows:
            parsed = parse_row(item)
            if parsed:
                batch.append(parsed)
                total_poems += 1
                total_verses += len(parsed["verses"])

        offset += BATCH_SIZE

        # POST batch when large enough
        if len(batch) >= IMPORT_BATCH:
            result = post_poems(batch)
            total_posted += len(batch)
            added = result.get("added", 0)
            skipped = result.get("skipped", 0)
            elapsed = time.time() - t0
            print(
                f"  offset={offset:>6} | posted={total_posted:>6} | "
                f"added={added:>4} skipped={skipped:>4} | "
                f"total_poems={total_poems:>6} verses={total_verses:>7} | "
                f"{elapsed:.0f}s"
            )
            if "error" in result:
                print(f"    ERROR: {result['error'][:200]}")
            batch = []
            time.sleep(0.5)

    # Post remaining
    if batch:
        result = post_poems(batch)
        total_posted += len(batch)
        print(f"  Final batch: {result}")

    elapsed = time.time() - t0
    print(f"\nDone! {total_poems} poems, {total_verses} verses fetched in {elapsed:.0f}s")
    print(f"Posted {total_posted} poems to backend")


if __name__ == "__main__":
    main()
