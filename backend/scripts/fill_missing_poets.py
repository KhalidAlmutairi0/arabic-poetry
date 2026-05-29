"""
Fill missing poets — compares HuggingFace dataset poets against DB,
inserts only the missing ones with their poems.
"""
import asyncio, sys, json, re, time, urllib.request, uuid
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

DB_URL = 'postgresql://postgres:hUlzaqTHKIjgUdEYuudRXmvusiBzgRQk@zephyr.proxy.rlwy.net:56773/railway'
HF_API = 'https://datasets-server.huggingface.co/rows'
METER_NAMES = ['البسيط','الخفيف','الرجز','الرمل','السريع','الطويل','الكامل','المتدارك','المتقارب','المجتث','المديد','المضارع','المقتضب','المنسرح','النثر','الهزج','الوافر']
ERA_MAP = {'العصر الجاهلي':'pre_islamic','الجاهلي':'pre_islamic','صدر الإسلام':'islamic_early','العصر الأموي':'umayyad','الأموي':'umayyad','العصر العباسي':'abbasid','العباسي':'abbasid','العصر الأندلسي':'andalusian','العصر المملوكي':'mamluk','العصر العثماني':'ottoman','العصر الحديث':'modern','الحديث':'modern','العصر المعاصر':'contemporary','المعاصر':'contemporary'}
TOTAL_ROWS = 212499

from unidecode import unidecode
from app.utils.arabic_normalizer import normalizer
import asyncpg

def map_era(s):
    for ar, slug in ERA_MAP.items():
        if ar in (s or ''): return slug
    return 'abbasid'

def make_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', unidecode(text).lower()).strip('-')[:200] or 'unknown'


async def main():
    conn = await asyncpg.connect(DB_URL)
    t0 = time.time()

    # Step 1: Get all existing poet slugs and poem slugs from DB
    print("Step 1: Loading existing data from DB...", flush=True)
    existing_poet_slugs = set(r['slug'] for r in await conn.fetch('SELECT slug FROM poets'))
    existing_poem_slugs = set(r['slug'] for r in await conn.fetch('SELECT slug FROM poems'))
    poets_before = len(existing_poet_slugs)
    print(f"  Existing poets: {poets_before}", flush=True)
    print(f"  Existing poems: {len(existing_poem_slugs)}", flush=True)

    # Step 2: Scan entire HuggingFace dataset to find all unique poets
    print("\nStep 2: Scanning HuggingFace dataset for all unique poets...", flush=True)
    all_hf_poets = {}  # slug -> {name, bio, era, poems: [...]}

    offset = 0
    while offset < TOTAL_ROWS:
        try:
            url = f'{HF_API}?dataset=arbml%2FAshaar_dataset&config=default&split=train&offset={offset}&length=100'
            data = json.loads(urllib.request.urlopen(url, timeout=30).read())
            rows = data.get('rows', [])
            if not rows:
                break
        except Exception as e:
            if '429' in str(e):
                print(f"  Rate limited at {offset}, waiting 60s...", flush=True)
                time.sleep(60)
                continue
            else:
                print(f"  HF error at {offset}: {e}", flush=True)
                time.sleep(3)
                continue

        for item in rows:
            row = item.get('row', {})
            poet_name = (row.get('poet_name') or '').strip()
            if not poet_name:
                continue

            poet_slug = make_slug(poet_name)

            # Only track poets NOT in DB
            if poet_slug in existing_poet_slugs:
                continue

            title = (row.get('poem_title') or '').strip()
            verses_list = row.get('poem_verses') or []
            raw_meter = row.get('poem_meter')
            era = (row.get('poet_era') or '').strip()
            poet_bio = (row.get('poet_description') or '').strip()[:500]

            if isinstance(raw_meter, int) and 0 <= raw_meter < len(METER_NAMES):
                meter = METER_NAMES[raw_meter]
            else:
                meter = None

            if not verses_list:
                continue

            poem_slug = f'{poet_slug}-{make_slug(title)}'[:580] if title else f'{poet_slug}-p-{offset}'
            if poem_slug in existing_poem_slugs:
                continue

            # Parse verses
            verses = []
            for v in verses_list:
                if not v or not isinstance(v, str) or len(v.strip()) < 3:
                    continue
                line = v.strip()
                h1, h2 = line, ''
                for sep in ['***', '\t', '   ']:
                    if sep in line:
                        parts = [p.strip() for p in line.split(sep, 1) if p.strip()]
                        if len(parts) == 2:
                            h1, h2 = parts
                        break
                verses.append((h1, h2))
            if not verses:
                continue

            if poet_slug not in all_hf_poets:
                all_hf_poets[poet_slug] = {
                    'name': poet_name,
                    'bio': poet_bio or 'شاعر عربي',
                    'era': map_era(era),
                    'poems': [],
                }

            all_hf_poets[poet_slug]['poems'].append({
                'title': title or verses[0][0][:60],
                'slug': poem_slug,
                'meter': meter,
                'era': map_era(era),
                'verses': verses,
            })
            existing_poem_slugs.add(poem_slug)

        offset += 100
        if offset % 5000 == 0:
            elapsed = time.time() - t0
            pct = (offset / TOTAL_ROWS) * 100
            print(f"  Scanned {offset}/{TOTAL_ROWS} ({pct:.1f}%) — found {len(all_hf_poets)} missing poets so far | {elapsed:.0f}s", flush=True)

    print(f"\nStep 2 complete: Found {len(all_hf_poets)} missing poets with poems", flush=True)

    if not all_hf_poets:
        print("No missing poets found! Database is complete.", flush=True)
        await conn.close()
        return

    # Step 3: Insert missing poets in batches of 25
    print(f"\nStep 3: Inserting {len(all_hf_poets)} missing poets in batches of 25...", flush=True)
    missing_poets = list(all_hf_poets.items())
    poets_added = 0
    poems_added = 0
    verses_added = 0

    for batch_start in range(0, len(missing_poets), 25):
        batch = missing_poets[batch_start:batch_start + 25]

        for i, (poet_slug, poet_data) in enumerate(batch):
            idx = batch_start + i + 1
            poet_name = poet_data['name']
            print(f"  Inserting missing poet {idx}/{len(missing_poets)}: {poet_name}", flush=True)

            # Insert poet
            poet_id = uuid.uuid4()
            await conn.execute(
                'INSERT INTO poets (id, name_ar, slug, bio_ar, era, nationality_ar, is_verified, poem_count, verse_count) '
                'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT (slug) DO NOTHING',
                poet_id, poet_name, poet_slug, poet_data['bio'], poet_data['era'], 'عربي', True, 0, 0
            )
            poets_added += 1

            # Insert poems + verses
            poet_poem_count = 0
            poet_verse_count = 0
            for poem_data in poet_data['poems']:
                poem_id = uuid.uuid4()
                full_text = '\n'.join(f'{h1} *** {h2}' if h2 else h1 for h1, h2 in poem_data['verses'])

                await conn.execute(
                    'INSERT INTO poems (id, poet_id, title_ar, slug, full_text, meter, verse_count, era, is_verified, is_published, source, view_count) '
                    'VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT (slug) DO NOTHING',
                    poem_id, poet_id, poem_data['title'], poem_data['slug'], full_text,
                    poem_data['meter'], len(poem_data['verses']), poem_data['era'],
                    True, True, 'ashaar/ARBML', 0
                )
                poems_added += 1
                poet_poem_count += 1

                verse_rows = []
                for pos, (h1, h2) in enumerate(poem_data['verses'], 1):
                    fv = f'{h1} *** {h2}' if h2 else h1
                    verse_rows.append((
                        uuid.uuid4(), poem_id, poet_id, pos,
                        h1, h2 or None, fv,
                        normalizer.normalize(fv),
                        normalizer.normalize(h1),
                        normalizer.normalize(h2) if h2 else None,
                        poet_name, poet_slug, poem_data['title'], poem_data['slug'],
                        False, False, 0, 0
                    ))
                    verses_added += 1
                    poet_verse_count += 1

                if verse_rows:
                    await conn.executemany(
                        'INSERT INTO verses (id, poem_id, poet_id, position, hemistich_1, hemistich_2, full_verse, '
                        'full_verse_normalized, hemistich_1_normalized, hemistich_2_normalized, '
                        'poet_name_ar, poet_slug, poem_title_ar, poem_slug, is_famous, is_verified, view_count, share_count) '
                        'VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18) ON CONFLICT DO NOTHING',
                        verse_rows
                    )

            # Update poet counts
            await conn.execute(
                'UPDATE poets SET poem_count = $1, verse_count = $2 WHERE id = $3',
                poet_poem_count, poet_verse_count, poet_id
            )

        print(f"  Batch done ({batch_start + len(batch)}/{len(missing_poets)}) — +{poets_added} poets, +{poems_added} poems, +{verses_added} verses", flush=True)

    await conn.close()
    elapsed = time.time() - t0

    print(f"\n{'='*50}", flush=True)
    print(f"  Total poets before: {poets_before}", flush=True)
    print(f"  Poets added now:    {poets_added}", flush=True)
    print(f"  Total poets after:  {poets_before + poets_added}", flush=True)
    print(f"  Poems added:        {poems_added}", flush=True)
    print(f"  Verses added:       {verses_added}", flush=True)
    print(f"  Time: {elapsed/60:.1f} min", flush=True)
    print(f"{'='*50}", flush=True)

asyncio.run(main())
