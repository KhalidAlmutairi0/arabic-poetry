"""
Fetch-only phase: collect poems from Qafiyah API into a JSON cache.
Does NOT need PostgreSQL or Docker — just saves to a JSON file.

Run:
    python -X utf8 scripts/fetch_only.py

When Docker is available, run deep_fetch.py to import from the cache.
"""

import asyncio
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

BASE = "https://api.qafiyah.com"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "deep_cache.json")

# ─────────────────────────────────────────────────────────────────────────────
# 300+ search terms — broad Arabic words found in classical poetry
# ─────────────────────────────────────────────────────────────────────────────

SEARCH_TERMS = [
    # Common nouns — nature
    "الشمس", "القمر", "النجوم", "الليل", "الصبح", "الفجر", "المساء",
    "الريح", "المطر", "البحر", "النهر", "الجبل", "الصحراء", "الغيم",
    "الورد", "الزهر", "النبت", "الماء", "الشجر", "الروض", "البستان",
    "الطير", "الحمام", "العصفور", "الغزال", "الظبي", "الأسد",
    # Common nouns — human
    "القلب", "الروح", "العين", "الوجه", "اليد", "الشعر",
    "الدم", "الدمع", "البكاء", "الضحك", "الجمال", "الحسن",
    # Emotions / concepts
    "الحب", "الهوى", "العشق", "الغرام", "الوجد", "الشوق",
    "الفراق", "الهجر", "الوصال", "الحنين", "الوجع", "الألم",
    "الحزن", "الفرح", "السعادة", "الأمل", "الحلم", "الوهم",
    # Time
    "الأيام", "الزمان", "الدهر", "الليالي", "السنين", "الأزمان",
    "الأمس", "اليوم", "الغد", "الآن",
    # War / valor
    "السيف", "الرمح", "الخيل", "الحرب", "الفخر", "الشجاعة",
    "البطل", "الجهاد", "النصر", "الظفر", "الفتح",
    # Religion / zuhd
    "الإيمان", "الدنيا", "الآخرة", "الجنة", "النار", "التقوى",
    "الزهد", "الصبر", "التوبة", "الدعاء", "الحمد",
    # Places
    "بغداد", "دمشق", "القاهرة", "مكة", "المدينة", "الأندلس",
    "الشام", "العراق", "مصر", "الحجاز", "اليمن", "المغرب",
    "الفرات", "دجلة", "النيل",
    # Famous female names (subjects of ghazal)
    "سعاد", "ليلى", "لبنى", "عبلة", "هند", "زينب", "سلمى",
    "رباب", "دعد", "مية", "نوار", "أسماء",
    # Praise / panegyric themes
    "المدح", "الكرم", "الجود", "السخاء", "الشرف", "المجد",
    "العلا", "المنزلة", "الرفعة",
    # Elegy themes
    "الرثاء", "الفقد", "المصيبة", "الفاجعة", "المأتم",
    # Common verb forms (past)
    "قالت", "قلت", "جاء", "ذهب", "رأيت", "سألت", "أجاب",
    "عاش", "مات", "رحل", "غاب", "بكيت", "ضحكت",
    # Common poetic openers / exclamations
    "يا ليل", "يا دار", "يا عين", "يا قلب", "يا نفس",
    "ألا يا", "هل تذكر", "أما زلت", "إذا ما", "كم من",
    "قفا نبك", "بانت سعاد", "ألا ليت", "لمن الديار",
    # Geometric / abstract
    "النور", "الظلام", "الأثر", "الذكر", "الصمت",
    "الصوت", "الكلام", "الشعر", "القصيد", "الأبيات",
    # Common Nabati/popular themes
    "الفزعة", "العرب", "القبيلة",
    # Additional classical themes
    "الطلل", "الأطلال", "الديار", "المنازل", "الرحلة",
    "الهجرة", "الغربة", "الوطن", "الأهل", "الأحباب",
    # Weather / season
    "الربيع", "الصيف", "الخريف", "الشتاء", "البرد", "الحر",
    # Body metaphors in poetry
    "الثغر", "الخد", "الصدغ", "القد", "الخصر",
    # Stars / constellations
    "النجم", "الكوكب", "الثريا", "الجوزاء", "الهلال", "البدر",
    # Common verbs (present)
    "أحب", "أهوى", "أبكي", "أرجو", "أخشى", "أظن",
    "يمشي", "يجري", "يطير", "يغني", "يبكي",
    # Metals / gems (used in description)
    "الذهب", "الفضة", "اللؤلؤ", "الياقوت", "الدر",
    # Animals used as metaphor
    "الحمامة", "النسر", "الصقر", "الثعلب",
    # Common adjectives
    "الجميل", "الحسناء", "الكريم", "الشريف", "النبيل",
    "المجنون", "العاقل", "الغيور", "الصبور", "الجريء",
    # Verbs in imperative
    "اسمع", "انظر", "تذكر", "افكر", "اصبر",
    # Common expressions
    "لا تحزن", "كن صبورا", "يا رب", "سبحان الله",
    # Historical figures (subjects of poems)
    "الرسول", "النبي", "علي", "الحسين", "عمر", "عثمان",
    # Love / longing themes
    "العاشق", "المعشوق", "الحبيب", "الغائب", "المسافر",
    # Death / eternity
    "الموت", "الفناء", "البقاء", "الأبد", "الخلود",
    # Travel / journey
    "السفر", "الطريق", "المسير", "الرحيل", "الوداع",
    # Food / drink (used in description & wine poetry)
    "الخمر", "الكأس", "الشراب", "النبيذ",
    # Cities / rivers
    "الكوفة", "البصرة", "الأنبار", "واسط", "الموصل",
    "الرقة", "حلب", "حمص", "طرابلس", "القيروان",
    # Fame / legacy
    "الشهرة", "الذكر", "التاريخ", "المجد", "الأثر",
    # More first-line fragments
    "ولما رأيت", "وكم قد رأيت", "أقول وقد", "ألا قاتل الله",
    "وما كنت", "فلا تيأس", "إذا كنت", "من لي بمثل",
    "يا من رأى", "سقى الله", "حياك الله", "رعاك الله",
    # EXTRA terms to reach more poems
    "الغدير", "الخليج", "الجزيرة", "النخل", "التين",
    "الرمال", "السحاب", "البرق", "الرعد", "المشرق", "المغرب",
    "الشرق", "الغرب", "الجنوب", "الشمال",
    "الأم", "الأب", "الابن", "الأخ", "البنت",
    "الصديق", "العدو", "الرفيق", "الجار",
    "المسجد", "القصر", "الدار", "الخيمة", "البيت",
    "السلام", "الحرية", "العدالة", "الكرامة",
    "المعلقات", "القصيدة", "الديوان", "الغناء",
    "عنترة", "زهير", "طرفة", "لبيد", "كعب",
    "حسان", "الفرزدق", "جرير", "الأخطل",
    "أبو تمام", "البحتري", "أبو العلاء", "المعري",
    "ابن زيدون", "ولادة", "الشنفرى", "تأبط شرا",
    "أحمد شوقي", "حافظ إبراهيم", "إيليا أبو ماضي",
    "الجواهري", "السياب", "البياتي", "أدونيس",
    "سميح القاسم", "فدوى طوقان", "غادة السمان",
    "الماغوط", "أمل دنقل", "صلاح عبد الصبور",
    # ─── Round 2: more search terms ───
    # Single Arabic letters (very broad)
    "با", "تا", "ثا", "جا", "حا", "خا", "دا", "ذا", "را", "زا",
    "سا", "شا", "صا", "ضا", "طا", "ظا", "عا", "غا", "فا", "قا",
    "كا", "لا", "ما", "نا", "ها", "وا", "يا",
    # More nature terms
    "الوادي", "التل", "السهل", "الغابة", "الحديقة", "الزيتون",
    "العنب", "الرمان", "التفاح", "النارنج", "الياسمين", "النرجس",
    "البنفسج", "الأقحوان", "السوسن", "الريحان", "العود", "المسك",
    # More human/body
    "الشفاه", "الجبين", "العنق", "الذراع", "الكف", "الأصابع",
    "الجسد", "البدن", "الظهر", "القامة",
    # More emotions
    "الغضب", "الخوف", "الرجاء", "اليأس", "الندم", "العتاب",
    "الصفح", "العفو", "الغفران", "الرحمة", "الشفقة",
    # Society
    "الملك", "الأمير", "الوزير", "القاضي", "الفقيه", "العالم",
    "التاجر", "الفلاح", "الراعي", "الصياد", "البحار",
    # Wisdom phrases
    "من جد", "لكل شيء", "ليس كل", "إن من", "رب ضارة",
    "خير الناس", "أعز الناس", "أجمل ما", "أحسن ما", "أعظم ما",
    # More verbs
    "وقفت", "جلست", "نظرت", "سمعت", "علمت", "عرفت",
    "حملت", "وضعت", "أعطيت", "أخذت", "كتبت", "قرأت",
    "فتحت", "أغلقت", "دخلت", "خرجت",
    # Specific meters (to find poems by meter)
    "بحر الطويل", "بحر البسيط", "بحر الكامل", "بحر الوافر",
    "بحر الرجز", "بحر الرمل", "بحر الخفيف",
    # Colors
    "الأبيض", "الأسود", "الأحمر", "الأخضر", "الأزرق", "الأصفر",
    # More places
    "طيبة", "يثرب", "عسقلان", "غرناطة", "قرطبة", "إشبيلية",
    "صنعاء", "عدن", "تونس", "فاس", "مراكش", "الجزائر",
    "بيروت", "صيدا", "طرابلس", "عمان", "القدس", "نابلس",
    "أصفهان", "شيراز", "سمرقند", "بخارى",
    # Musical instruments (in poetry)
    "العود", "الناي", "الدف", "الربابة", "المزمار",
    # Clothing/adornment
    "الثوب", "الرداء", "العمامة", "التاج", "الخاتم",
    "القلادة", "السوار", "الحلي",
    # Common poetic particles/openers
    "أيا", "أفلا", "ألم تر", "ألست", "أما آن",
    "لعمرك", "لعمري", "بالله", "تالله",
    # Abstract concepts
    "العقل", "الجهل", "العلم", "الحكم", "القدر",
    "الأجل", "الرزق", "النعمة", "البلاء", "الابتلاء",
    # Architecture
    "المنارة", "القبة", "الجسر", "السور", "الباب",
    "النافذة", "المحراب", "المنبر",
    # Sea/water
    "الموج", "الشاطئ", "المرسى", "السفينة", "الشراع",
    "الغوص", "اللؤلؤة", "المرجان",
    # Garden/agriculture
    "الحقل", "الزرع", "الحصاد", "الثمر", "الغصن",
    "الجذر", "الساق", "الورقة", "البذرة",
    # More poet names
    "الشريف الرضي", "ابن الرومي", "أبو فراس", "ابن المقفع",
    "الثعالبي", "ابن خلدون", "ابن بطوطة", "الطغرائي",
    "ابن الفارض", "ابن عربي", "الحلاج", "رابعة العدوية",
    "ابن حزم", "الجاحظ", "المتنبي", "أبو العتاهية",
    "بشار بن برد", "ديك الجن", "الشريف المرتضى",
    "صفي الدين الحلي", "ابن نباتة", "ابن سناء الملك",
    # Quranic/religious references in poetry
    "الفردوس", "الكوثر", "الحوض", "الصراط", "الميزان",
    "القيامة", "البعث", "الحشر", "الحساب",
]

# Deduplicate
seen = set()
SEARCH_TERMS = [t for t in SEARCH_TERMS if not (t in seen or seen.add(t))]


async def fetch_poems_for_term(client, term, max_pages=5):
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
            if not data.get("pagination", {}).get("hasNextPage", False):
                break
            await asyncio.sleep(0.25)
        except Exception:
            break
    return results


def save_cache(poems, completed_terms):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"poems": poems, "completed_terms": list(completed_terms)},
            f, ensure_ascii=False
        )


async def main():
    # Load existing cache
    all_poems = {}
    completed_terms = set()

    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                cache = json.load(f)
            all_poems = cache.get("poems", {})
            completed_terms = set(cache.get("completed_terms", []))
            print(f"Resuming from cache: {len(all_poems)} poems, {len(completed_terms)} terms done")
        except Exception:
            pass

    remaining = [t for t in SEARCH_TERMS if t not in completed_terms]
    print(f"Total terms: {len(SEARCH_TERMS)}, remaining: {len(remaining)}")

    if not remaining:
        print("All terms done! Nothing to fetch.")
        return

    limits = httpx.Limits(max_connections=3, max_keepalive_connections=2)
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; poetry-bot/2.0)"},
        limits=limits,
    ) as client:
        for i, term in enumerate(remaining, 1):
            results = await fetch_poems_for_term(client, term)
            new_count = 0
            for poem in results:
                slug = poem.get("poem_slug", "")
                if slug and slug not in all_poems:
                    all_poems[slug] = poem
                    new_count += 1

            completed_terms.add(term)
            total = len(all_poems)
            print(
                f"  [{i:>3}/{len(remaining)}] {term[:20]:<20} +{new_count:>4} new  total={total:>6}",
                flush=True,
            )

            if i % 20 == 0:
                save_cache(all_poems, completed_terms)
                print(f"  --- Checkpoint saved ({total} poems) ---")

            await asyncio.sleep(0.4)

    save_cache(all_poems, completed_terms)
    print(f"\nDone! Collected {len(all_poems)} unique poems from {len(completed_terms)} search terms.")
    print(f"Saved to: {CACHE_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
