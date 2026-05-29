"""Fast direct import into Neon - optimized for speed."""
import asyncio, sys, json, re, time, urllib.request
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')

DB_URL = 'postgresql+asyncpg://neondb_owner:npg_hHQByvIeWi98@ep-wispy-star-aquhewsa.c-8.us-east-1.aws.neon.tech/neondb?ssl=require'
HF_API = 'https://datasets-server.huggingface.co/rows'
METER_NAMES = ['البسيط','الخفيف','الرجز','الرمل','السريع','الطويل','الكامل','المتدارك','المتقارب','المجتث','المديد','المضارع','المقتضب','المنسرح','النثر','الهزج','الوافر']
ERA_MAP = {'العصر الجاهلي':'pre_islamic','الجاهلي':'pre_islamic','صدر الإسلام':'islamic_early','العصر الأموي':'umayyad','الأموي':'umayyad','العصر العباسي':'abbasid','العباسي':'abbasid','العصر الأندلسي':'andalusian','العصر المملوكي':'mamluk','العصر العثماني':'ottoman','العصر الحديث':'modern','الحديث':'modern','العصر المعاصر':'contemporary','المعاصر':'contemporary'}

from unidecode import unidecode

def map_era(s):
    for ar, slug in ERA_MAP.items():
        if ar in (s or ''): return slug
    return 'abbasid'

def make_slug(text):
    return re.sub(r'[^a-z0-9]+', '-', unidecode(text).lower()).strip('-')[:200] or 'unknown'

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text
from app.core.database import Base
from app.models import Poet, Poem, Verse, Category
from app.utils.arabic_normalizer import normalizer
import app.models

engine = create_async_engine(DB_URL, pool_size=3, max_overflow=5)

async def main():
    Session = async_sessionmaker(engine, expire_on_commit=False)
    t0 = time.time()

    # Load existing slugs into memory
    async with Session() as session:
        existing_poem_slugs = set(r[0] for r in (await session.execute(select(Poem.slug))).fetchall())
        poet_cache = {}
        for p in (await session.execute(select(Poet))).scalars().all():
            poet_cache[p.slug] = p
    print(f'Existing: {len(existing_poem_slugs)} poems, {len(poet_cache)} poets')

    total_poets = len(poet_cache)
    total_poems = len(existing_poem_slugs)
    total_verses = 0
    start_offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    offset = start_offset
    while offset < 212500:
        # Fetch from HuggingFace
        try:
            url = f'{HF_API}?dataset=arbml%2FAshaar_dataset&config=default&split=train&offset={offset}&length=100'
            data = json.loads(urllib.request.urlopen(url, timeout=30).read())
            rows = data.get('rows', [])
            if not rows:
                print(f'No more rows at offset {offset}')
                break
        except Exception as e:
            print(f'HF error at {offset}: {e}')
            if '429' in str(e):
                print('Rate limited, waiting 60s...')
                time.sleep(60)
            else:
                time.sleep(3)
            continue

        batch_added = 0
        async with Session() as session:
            for item in rows:
                row = item.get('row', {})
                poet_name = (row.get('poet_name') or '').strip()
                title = (row.get('poem_title') or '').strip()
                verses_list = row.get('poem_verses') or []
                raw_meter = row.get('poem_meter')
                era = (row.get('poet_era') or '').strip()
                poet_bio = (row.get('poet_description') or '').strip()[:500]

                if isinstance(raw_meter, int) and 0 <= raw_meter < len(METER_NAMES):
                    meter = METER_NAMES[raw_meter]
                else:
                    meter = None

                if not poet_name or not verses_list:
                    continue

                poet_slug = make_slug(poet_name)
                poem_slug = f'{poet_slug}-{make_slug(title)}'[:580] if title else f'{poet_slug}-poem-{offset}'

                if poem_slug in existing_poem_slugs:
                    continue

                # Get or create poet (from cache)
                if poet_slug not in poet_cache:
                    poet = Poet(name_ar=poet_name, slug=poet_slug, bio_ar=poet_bio or 'شاعر عربي', era=map_era(era), nationality_ar='عربي', is_verified=True, poem_count=0, verse_count=0)
                    session.add(poet)
                    await session.flush()
                    poet_cache[poet_slug] = poet
                    total_poets += 1
                poet = poet_cache[poet_slug]

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

                full_text = '\n'.join(f'{h1} *** {h2}' if h2 else h1 for h1, h2 in verses)
                poem = Poem(poet_id=poet.id, title_ar=title or verses[0][0][:60], slug=poem_slug, full_text=full_text, meter=meter, verse_count=len(verses), era=map_era(era), is_verified=True, is_published=True, source='ashaar/ARBML')
                session.add(poem)
                await session.flush()
                existing_poem_slugs.add(poem_slug)

                for pos, (h1, h2) in enumerate(verses, 1):
                    fv = f'{h1} *** {h2}' if h2 else h1
                    session.add(Verse(poem_id=poem.id, poet_id=poet.id, position=pos, hemistich_1=h1, hemistich_2=h2 or None, full_verse=fv, full_verse_normalized=normalizer.normalize(fv), hemistich_1_normalized=normalizer.normalize(h1), hemistich_2_normalized=normalizer.normalize(h2) if h2 else None, poet_name_ar=poet_name, poet_slug=poet_slug, poem_title_ar=title, poem_slug=poem_slug, is_famous=False))
                    total_verses += 1

                total_poems += 1
                batch_added += 1
                poet.poem_count = (poet.poem_count or 0) + 1
                poet.verse_count = (poet.verse_count or 0) + len(verses)

            await session.commit()

        offset += 100
        if offset % 500 == 0:
            elapsed = time.time() - t0
            print(f'offset={offset:>6} | poets={total_poets:>4} poems={total_poems:>6} verses={total_verses:>8} | +{batch_added} | {elapsed:.0f}s', flush=True)

    print(f'\nDONE! {total_poets} poets, {total_poems} poems, {total_verses} verses in {time.time()-t0:.0f}s', flush=True)

asyncio.run(main())
