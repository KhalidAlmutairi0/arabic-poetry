"""
Seed script — populate the database with initial poetry data.
Run: python scripts/seed_data.py

Contains real famous Arabic poems to kickstart the platform.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models import Poet, Poem, Verse, Category, PoemCategory
from app.utils.arabic_normalizer import normalizer, arabic_to_slug
import uuid

engine = create_async_engine(settings.database_url)
Session = async_sessionmaker(engine, expire_on_commit=False)

# ── Seed Data ─────────────────────────────────────────

CATEGORIES = [
    {"name_ar": "الغزل والحب",   "name_en": "Love",        "slug": "love",       "icon": "❤️", "color": "#E74C3C", "display_order": 1},
    {"name_ar": "الحكمة",        "name_en": "Wisdom",      "slug": "wisdom",     "icon": "🌙", "color": "#8E44AD", "display_order": 2},
    {"name_ar": "الفخر",         "name_en": "Pride",       "slug": "pride",      "icon": "⚔️", "color": "#E67E22", "display_order": 3},
    {"name_ar": "الرثاء",        "name_en": "Elegy",       "slug": "elegy",      "icon": "🕊️", "color": "#95A5A6", "display_order": 4},
    {"name_ar": "الشوق والحنين", "name_en": "Longing",     "slug": "longing",    "icon": "🌊", "color": "#3498DB", "display_order": 5},
    {"name_ar": "الوصف",         "name_en": "Description", "slug": "description","icon": "🌿", "color": "#27AE60", "display_order": 6},
    {"name_ar": "الفلسفة",       "name_en": "Philosophy",  "slug": "philosophy", "icon": "⚡", "color": "#2C3E50", "display_order": 7},
    {"name_ar": "المدح",         "name_en": "Praise",      "slug": "praise",     "icon": "👑", "color": "#F1C40F", "display_order": 8},
    {"name_ar": "الطبيعة",       "name_en": "Nature",      "slug": "nature",     "icon": "🌸", "color": "#1ABC9C", "display_order": 9},
    {"name_ar": "الهجاء",        "name_en": "Satire",      "slug": "satire",     "icon": "🗡️", "color": "#C0392B", "display_order": 10},
]

POETS = [
    {
        "name_ar": "أبو الطيب المتنبي",
        "name_en": "Al-Mutanabbi",
        "slug": "almutanabbi",
        "bio_ar": "أحمد بن الحسين الجعفي الكندي، أبو الطيب المتنبي (303-354 هـ). يُعدّ من أعظم شعراء العرب على الإطلاق. اشتُهر بفخره وحكمته وشجاعته وصدق تجربته الشعرية.",
        "era": "abbasid",
        "birth_year": 915,
        "death_year": 965,
        "birth_place_ar": "الكوفة، العراق",
        "nationality_ar": "عربي",
        "is_verified": True,
    },
    {
        "name_ar": "أبو نواس",
        "name_en": "Abu Nuwas",
        "slug": "abunuwas",
        "bio_ar": "الحسن بن هانئ الحكمي، أبو نواس (145-198 هـ). من أشهر شعراء العصر العباسي، عُرف بشعر الخمر والغزل والمجون.",
        "era": "abbasid",
        "birth_year": 762,
        "death_year": 813,
        "birth_place_ar": "الأهواز، فارس",
        "nationality_ar": "عربي",
        "is_verified": True,
    },
    {
        "name_ar": "امرؤ القيس",
        "name_en": "Imru al-Qays",
        "slug": "imrualqays",
        "bio_ar": "امرؤ القيس بن حُجر الكندي (501-540م). شاعر جاهلي يُلقَّب بالملك الضِّلِّيل، وصاحب إحدى المعلقات السبع الشهيرة.",
        "era": "pre_islamic",
        "death_year": 540,
        "birth_place_ar": "نجد، شبه الجزيرة العربية",
        "nationality_ar": "عربي",
        "is_verified": True,
    },
    {
        "name_ar": "الخنساء",
        "name_en": "Al-Khansa",
        "slug": "alkhansa",
        "bio_ar": "تُماضر بنت عمرو بن الحارث السُّلمية، الخنساء (575-664م). أعظم شاعرات العرب، اشتهرت برثاء أخيها صخر.",
        "era": "pre_islamic",
        "birth_year": 575,
        "death_year": 664,
        "birth_place_ar": "نجد، شبه الجزيرة العربية",
        "nationality_ar": "عربية",
        "is_verified": True,
    },
    {
        "name_ar": "محمود درويش",
        "name_en": "Mahmoud Darwish",
        "slug": "mahmouddarwish",
        "bio_ar": "محمود درويش (1941-2008م). الشاعر الفلسطيني الكبير، رمز المقاومة والهوية العربية، أحد أبرز شعراء القرن العشرين.",
        "era": "contemporary",
        "birth_year": 1941,
        "death_year": 2008,
        "birth_place_ar": "البروة، فلسطين",
        "nationality_ar": "فلسطيني",
        "is_verified": True,
    },
    {
        "name_ar": "نزار قباني",
        "name_en": "Nizar Qabbani",
        "slug": "nizarqabbani",
        "bio_ar": "نزار قباني (1923-1998م). الشاعر السوري الذي قدّم الحب والمرأة والسياسة بأسلوب ثوري. يُعدّ من أكثر الشعراء العرب قراءةً في القرن العشرين.",
        "era": "contemporary",
        "birth_year": 1923,
        "death_year": 1998,
        "birth_place_ar": "دمشق، سوريا",
        "nationality_ar": "سوري",
        "is_verified": True,
    },
]

POEMS_DATA = [
    {
        "poet_slug": "almutanabbi",
        "title_ar": "على قدر أهل العزم",
        "slug": "almutanabbi-ala-qadri-ahlil-azm",
        "meter": "البسيط",
        "era": "abbasid",
        "is_verified": True,
        "categories": ["pride", "wisdom"],
        "verses": [
            {"h1": "عَلى قَدرِ أَهلِ العَزمِ تَأتي العَزائِمُ", "h2": "وَتَأتي عَلى قَدرِ الكِرامِ المَكارِمُ", "famous": True},
            {"h1": "وَتَعظُمُ في عَينِ الصَغيرِ صِغارُها", "h2": "وَتَصغُرُ في عَينِ العَظيمِ العَظائِمُ", "famous": True},
            {"h1": "يُكَلِّفُ سَيفُ الدَولَةِ الجَيشَ هَمَّهُ", "h2": "وَقَد عَجَزَت عَنهُ الجُيوشُ الخَضارِمُ"},
            {"h1": "وَيَطلُبُ عِندَ النّاسِ ما عِندَ نَفسِهِ", "h2": "وَذلِكَ ما لا تَدَّعيهِ الضَراغِمُ"},
            {"h1": "وَلَم أَرَ في عُيوبِ النّاسِ عَيباً", "h2": "كَنَقصِ القادِرينَ عَلَى التَمامِ", "famous": True},
        ],
    },
    {
        "poet_slug": "almutanabbi",
        "title_ar": "الخيل والليل والبيداء",
        "slug": "almutanabbi-alkhayl-wallayl",
        "meter": "الطويل",
        "era": "abbasid",
        "is_verified": True,
        "categories": ["pride", "description"],
        "verses": [
            {"h1": "الخَيلُ وَاللَيلُ وَالبَيداءُ تَعرِفُني", "h2": "وَالسَيفُ وَالرُمحُ وَالقِرطاسُ وَالقَلَمُ", "famous": True},
            {"h1": "صَحِبتُ في الفَلَواتِ الوَحشَ مُنفَرِداً", "h2": "حَتّى تَعَجَّبَ مِنّي القُورُ وَالأَكَمُ"},
            {"h1": "يا مَن يَعِزُّ عَلَينا أَن نُفارِقَهُم", "h2": "وِجدانُنا كُلَّ شَيءٍ بَعدَكُم عَدَمُ"},
        ],
    },
    {
        "poet_slug": "almutanabbi",
        "title_ar": "أنا الذي نظر الأعمى إلى أدبي",
        "slug": "almutanabbi-ana-allathi",
        "meter": "الكامل",
        "era": "abbasid",
        "is_verified": True,
        "categories": ["pride"],
        "verses": [
            {"h1": "أَنا الَّذي نَظَرَ الأَعمى إِلى أَدَبي", "h2": "وَأَسمَعَت كَلِماتي مَن بِهِ صَمَمُ", "famous": True},
            {"h1": "أَنامُ مِلءَ جُفوني عَن شَوارِدِها", "h2": "وَيَسهَرُ الخَلقُ جَرّاها وَيَختَصِمُ", "famous": True},
            {"h1": "وَجاهِلٍ مَدَّهُ في جَهلِهِ ضَحِكي", "h2": "حَتّى أَتَتهُ يَدٌ فَرّاسَةٌ وَفَمُ"},
        ],
    },
    {
        "poet_slug": "imrualqays",
        "title_ar": "معلقة امرئ القيس",
        "slug": "imrualqays-muallaqah",
        "meter": "الطويل",
        "era": "pre_islamic",
        "is_verified": True,
        "categories": ["love", "description"],
        "verses": [
            {"h1": "قِفا نَبكِ مِن ذِكرى حَبيبٍ وَمَنزِلِ", "h2": "بِسِقطِ اللِوى بَينَ الدَخولِ فَحَومَلِ", "famous": True},
            {"h1": "فَتوضَحَ فَالمِقراةِ لَم يَعفُ رَسمُها", "h2": "لِما نَسَجَتها مِن جَنوبٍ وَشَمأَلِ"},
            {"h1": "أَلا عِم صَباحاً أَيُّها الطَلَلُ البالي", "h2": "وَهَل يَعِمَنَّ مَن كانَ في العُصُرِ الخالي"},
            {"h1": "وَإِنَّ شِفائي عَبرَةٌ مُهَراقَةٌ", "h2": "فَهَل عِندَ رَسمٍ دارِسٍ مِن مُعَوَّلِ", "famous": True},
        ],
    },
    {
        "poet_slug": "alkhansa",
        "title_ar": "رثاء أخيها صخر",
        "slug": "alkhansa-rithaa-sakhr",
        "meter": "الوافر",
        "era": "pre_islamic",
        "is_verified": True,
        "categories": ["elegy"],
        "verses": [
            {"h1": "وَإِنَّ صَخراً لَتَأتَمُّ الهُداةُ بِهِ", "h2": "كَأَنَّهُ عَلَمٌ في رَأسِهِ نارُ", "famous": True},
            {"h1": "طَويلُ النِجادِ رَفيعُ العِمادِ", "h2": "سادَ عَشيرَتَهُ أَمرَدا"},
            {"h1": "قَذى بِعَينِكِ أَم بِالعَينِ عُوّارُ", "h2": "أَم ذَرَفَت إِذ خَلَت مِن أَهلِها الدّارُ", "famous": True},
        ],
    },
    {
        "poet_slug": "mahmouddarwish",
        "title_ar": "على هذه الأرض ما يستحق الحياة",
        "slug": "darwish-ala-hathihi-alarth",
        "meter": "التفعيلة",
        "era": "contemporary",
        "is_verified": True,
        "categories": ["longing", "philosophy"],
        "verses": [
            {"h1": "على هذه الأرض ما يستحق الحياة", "h2": "", "famous": True},
            {"h1": "على هذه الأرض سيدة الأرض أم الابتداء", "h2": ""},
            {"h1": "وللأرض عندي ما يستحق الحياة", "h2": "", "famous": True},
        ],
    },
    {
        "poet_slug": "nizarqabbani",
        "title_ar": "أنثى",
        "slug": "qabbani-untha",
        "meter": "التفعيلة",
        "era": "contemporary",
        "is_verified": True,
        "categories": ["love"],
        "verses": [
            {"h1": "أنتِ يا امرأة لا أقوى على تركك", "h2": "", "famous": True},
            {"h1": "كالبحر لا أقوى على تركه", "h2": ""},
            {"h1": "وكالشعر والعطر والموسيقى", "h2": "", "famous": True},
        ],
    },
]


async def seed(session: AsyncSession):
    print("🌱 Seeding categories...")
    cat_map = {}
    for cat_data in CATEGORIES:
        cat = Category(**cat_data)
        session.add(cat)
        await session.flush()
        cat_map[cat_data["slug"]] = cat
    print(f"  ✅ {len(CATEGORIES)} categories created")

    print("🌱 Seeding poets...")
    poet_map = {}
    for poet_data in POETS:
        poet = Poet(**poet_data)
        session.add(poet)
        await session.flush()
        poet_map[poet_data["slug"]] = poet
    print(f"  ✅ {len(POETS)} poets created")

    print("🌱 Seeding poems and verses...")
    total_verses = 0
    for poem_data in POEMS_DATA:
        poet_slug_key = poem_data["poet_slug"]
        poet = poet_map[poet_slug_key]
        poem_data = dict(poem_data)  # copy so we don't mutate the global list
        poem_data.pop("poet_slug")   # not a Poem column
        verses_raw = poem_data.pop("verses")
        categories_slugs = poem_data.pop("categories", [])

        full_text = "\n".join(
            f"{v['h1']} *** {v.get('h2', '')}" for v in verses_raw
        )

        poem = Poem(
            poet_id=poet.id,
            full_text=full_text,
            **{k: v for k, v in poem_data.items()},
        )
        session.add(poem)
        await session.flush()

        # Attach categories
        for cat_slug in categories_slugs:
            if cat_slug in cat_map:
                pc = PoemCategory(poem_id=poem.id, category_id=cat_map[cat_slug].id)
                session.add(pc)

        # Create verses
        for i, vd in enumerate(verses_raw, start=1):
            h1 = vd["h1"]
            h2 = vd.get("h2", "")
            full_verse = f"{h1} *** {h2}" if h2 else h1

            verse = Verse(
                poem_id=poem.id,
                poet_id=poet.id,
                position=i,
                hemistich_1=h1,
                hemistich_2=h2 if h2 else None,
                full_verse=full_verse,
                full_verse_normalized=normalizer.normalize(full_verse),
                hemistich_1_normalized=normalizer.normalize(h1),
                hemistich_2_normalized=normalizer.normalize(h2) if h2 else None,
                poet_name_ar=poet.name_ar,
                poet_slug=poet.slug,
                poem_title_ar=poem.title_ar,
                poem_slug=poem.slug,
                is_famous=vd.get("famous", False),
            )
            session.add(verse)
            total_verses += 1

        poet.poem_count += 1
        poem.verse_count = len(verses_raw)

    await session.commit()
    print(f"  ✅ {len(POEMS_DATA)} poems, {total_verses} verses created")
    print("✅ Seeding complete!")


async def index_to_meilisearch(session):
    """Index all verses and poets to Meilisearch for search."""
    try:
        from meilisearch_python_sdk import AsyncClient
        from sqlalchemy import select

        meili_url = settings.meilisearch_url
        meili_key = settings.meilisearch_key

        print("📦 Indexing to Meilisearch...")

        async with AsyncClient(url=meili_url, api_key=meili_key) as client:
            # Index verses
            verses_result = await session.execute(select(Verse))
            verses = list(verses_result.scalars().all())

            verse_docs = [
                {
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
                }
                for v in verses
            ]

            if verse_docs:
                verses_index = client.index("verses")
                await verses_index.add_documents(verse_docs, primary_key="id")
                print(f"  ✅ Indexed {len(verse_docs)} verses")

            # Index poets
            poets_result = await session.execute(select(Poet))
            poets = list(poets_result.scalars().all())

            poet_docs = [
                {
                    "id": str(p.id),
                    "name_ar": p.name_ar,
                    "name_en": p.name_en or "",
                    "slug": p.slug,
                    "era": p.era or "",
                    "bio_ar": (p.bio_ar or "")[:200],
                    "poem_count": p.poem_count,
                }
                for p in poets
            ]

            if poet_docs:
                poets_index = client.index("poets")
                await poets_index.add_documents(poet_docs)
                print(f"  ✅ Indexed {len(poet_docs)} poets")

    except Exception as e:
        print(f"  ⚠️  Meilisearch indexing failed (is it running?): {e}")
        print("     Run the seed again when Meilisearch is available, or index manually.")


async def main():
    # Enable extensions (non-fatal if pgvector not installed)
    from sqlalchemy import text
    async with engine.begin() as conn:
        try:
            await conn.execute(text("""
                DO $$
                BEGIN
                    CREATE EXTENSION IF NOT EXISTS vector;
                EXCEPTION WHEN OTHERS THEN
                    RAISE WARNING 'pgvector not available';
                END $$
            """))
        except Exception:
            pass
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        except Exception:
            pass

    # Create tables
    from app.core.database import Base
    import app.models  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        await seed(session)
        # Index to Meilisearch (non-critical — can fail if Meili is not running)
        await index_to_meilisearch(session)


if __name__ == "__main__":
    asyncio.run(main())
