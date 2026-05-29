"""Ultra-fast Neon import using raw SQL bulk inserts."""
import asyncio, sys, json, re, time, urllib.request, uuid
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

DB_URL = 'postgresql://postgres:HaqHSzZSdDtxPTGzoDJrVfJppTMHtrOe@zephyr.proxy.rlwy.net:56733/railway'
HF_API = 'https://datasets-server.huggingface.co/rows'
METER_NAMES = ['البسيط','الخفيف','الرجز','الرمل','السريع','الطويل','الكامل','المتدارك','المتقارب','المجتث','المديد','المضارع','المقتضب','المنسرح','النثر','الهزج','الوافر']
ERA_MAP = {'العصر الجاهلي':'pre_islamic','الجاهلي':'pre_islamic','صدر الإسلام':'islamic_early','العصر الأموي':'umayyad','الأموي':'umayyad','العصر العباسي':'abbasid','العباسي':'abbasid','العصر الأندلسي':'andalusian','العصر المملوكي':'mamluk','العصر العثماني':'ottoman','العصر الحديث':'modern','الحديث':'modern','العصر المعاصر':'contemporary','المعاصر':'contemporary'}
TOTAL = 212499

from unidecode import unidecode
from app.utils.arabic_normalizer import normalizer

def map_era(s):
    for ar, slug in ERA_MAP.items():
        if ar in (s or ''): return slug
    return 'abbasid'

def make_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', unidecode(text).lower()).strip('-')[:200] or 'unknown'

import asyncpg

async def main():
    conn = await asyncpg.connect(DB_URL)
    t0 = time.time()

    # Load existing
    existing_poems = set(r['slug'] for r in await conn.fetch('SELECT slug FROM poems'))
    poet_rows = await conn.fetch('SELECT id, slug, name_ar FROM poets')
    poet_map = {r['slug']: (r['id'], r['name_ar']) for r in poet_rows}
    print(f'Existing: {len(existing_poems)} poems, {len(poet_map)} poets', flush=True)

    start_offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    offset = start_offset
    total_added = 0
    total_verses = 0

    while offset < TOTAL:
        try:
            url = f'{HF_API}?dataset=arbml%2FAshaar_dataset&config=default&split=train&offset={offset}&length=100'
            data = json.loads(urllib.request.urlopen(url, timeout=30).read())
            rows = data.get('rows', [])
            if not rows:
                print(f'No more rows at {offset}', flush=True)
                break
        except Exception as e:
            if '429' in str(e):
                print(f'Rate limited at {offset}, waiting 60s...', flush=True)
                time.sleep(60)
            else:
                print(f'HF error at {offset}: {e}', flush=True)
                time.sleep(3)
            continue

        # Collect batch data
        poets_to_add = []
        poems_to_add = []
        verses_to_add = []

        for item in rows:
            row = item.get('row', {})
            poet_name = (row.get('poet_name') or '').strip()
            title = (row.get('poem_title') or '').strip()
            verses_list = row.get('poem_verses') or []
            raw_meter = row.get('poem_meter')
            era = (row.get('poet_era') or '').strip()
            poet_bio = (row.get('poet_description') or '').strip()[:500]

            meter = METER_NAMES[raw_meter] if isinstance(raw_meter, int) and 0 <= raw_meter < len(METER_NAMES) else None
            if not poet_name or not verses_list: continue

            poet_slug = make_slug(poet_name)
            poem_slug = f'{poet_slug}-{make_slug(title)}'[:580] if title else f'{poet_slug}-p-{offset}'
            if poem_slug in existing_poems: continue

            # Ensure poet exists
            if poet_slug not in poet_map:
                pid = uuid.uuid4()
                poets_to_add.append((pid, poet_name, poet_slug, poet_bio or 'شاعر عربي', map_era(era), 'عربي', True, 0, 0))
                poet_map[poet_slug] = (pid, poet_name)

            poet_id, poet_name_ar = poet_map[poet_slug]

            # Parse verses
            verses = []
            for v in verses_list:
                if not v or not isinstance(v, str) or len(v.strip()) < 3: continue
                line = v.strip()
                h1, h2 = line, ''
                for sep in ['***', '\t', '   ']:
                    if sep in line:
                        parts = [p.strip() for p in line.split(sep, 1) if p.strip()]
                        if len(parts) == 2: h1, h2 = parts
                        break
                verses.append((h1, h2))
            if not verses: continue

            full_text = '\n'.join(f'{h1} *** {h2}' if h2 else h1 for h1, h2 in verses)
            poem_id = uuid.uuid4()
            poems_to_add.append((poem_id, poet_id, title or verses[0][0][:60], poem_slug, full_text, meter, len(verses), map_era(era), True, True, 'ashaar/ARBML', 0))
            existing_poems.add(poem_slug)

            for pos, (h1, h2) in enumerate(verses, 1):
                fv = f'{h1} *** {h2}' if h2 else h1
                verses_to_add.append((uuid.uuid4(), poem_id, poet_id, pos, h1, h2 or None, fv, normalizer.normalize(fv), normalizer.normalize(h1), normalizer.normalize(h2) if h2 else None, poet_name_ar, poet_slug, title, poem_slug, False, False, 0, 0))

        # Bulk insert
        if poets_to_add:
            await conn.executemany(
                'INSERT INTO poets (id, name_ar, slug, bio_ar, era, nationality_ar, is_verified, poem_count, verse_count) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (slug) DO NOTHING',
                poets_to_add
            )

        if poems_to_add:
            await conn.executemany(
                'INSERT INTO poems (id, poet_id, title_ar, slug, full_text, meter, verse_count, era, is_verified, is_published, source, view_count) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) ON CONFLICT (slug) DO NOTHING',
                poems_to_add
            )
            total_added += len(poems_to_add)

        if verses_to_add:
            await conn.executemany(
                'INSERT INTO verses (id, poem_id, poet_id, position, hemistich_1, hemistich_2, full_verse, full_verse_normalized, hemistich_1_normalized, hemistich_2_normalized, poet_name_ar, poet_slug, poem_title_ar, poem_slug, is_famous, is_verified, view_count, share_count) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18) ON CONFLICT DO NOTHING',
                verses_to_add
            )
            total_verses += len(verses_to_add)

        offset += 100
        if offset % 500 == 0:
            elapsed = time.time() - t0
            pct = (offset / TOTAL) * 100
            eta = (elapsed / max(offset - start_offset, 1)) * (TOTAL - offset) / 60
            print(f'{pct:5.1f}% | offset={offset:>6}/{TOTAL} | +{total_added:>6} poems +{total_verses:>8} verses | {len(poet_map)} poets | {elapsed:.0f}s | ETA {eta:.0f}min', flush=True)

    await conn.close()
    print(f'\nDONE! +{total_added} poems, +{total_verses} verses in {(time.time()-t0)/60:.1f}min', flush=True)

asyncio.run(main())
