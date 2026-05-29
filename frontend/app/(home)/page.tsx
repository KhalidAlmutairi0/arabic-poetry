import type { Metadata } from "next";
import Link from "next/link";
import { SearchBar } from "@/components/search/SearchBar";
import { VerseCard } from "@/components/poetry/VerseCard";
import { PoetCard } from "@/components/poetry/PoetCard";
import { CategoryGrid } from "@/components/poetry/CategoryGrid";
import { api } from "@/lib/api/client";

export const revalidate = 3600; // ISR: revalidate every hour

export const metadata: Metadata = {
  title: "شعر — محرك بحث الشعر العربي",
  description: "ابحث في الشعر العربي، اكتشف الأبيات بالمعنى والسياق، واستمتع بشرح ذكي للأبيات الصعبة.",
};

async function getFeaturedData() {
  try {
    const [versesRes, poetsRes, catsRes] = await Promise.allSettled([
      api.get("/api/v1/verses/famous?limit=5"),
      api.get("/api/v1/poets?limit=8"),
      api.get("/api/v1/categories"),
    ]);

    return {
      verses:     versesRes.status === "fulfilled" ? (Array.isArray(versesRes.value) ? versesRes.value : []) : FALLBACK_VERSES,
      poets:      poetsRes.status === "fulfilled"  ? poetsRes.value?.items || [] : FALLBACK_POETS,
      categories: catsRes.status === "fulfilled"   ? (Array.isArray(catsRes.value) ? catsRes.value : []) : FALLBACK_CATEGORIES,
    };
  } catch {
    return { verses: FALLBACK_VERSES, poets: FALLBACK_POETS, categories: FALLBACK_CATEGORIES };
  }
}

export default async function HomePage() {
  const { verses, poets, categories } = await getFeaturedData();

  return (
    <div className="flex flex-col" dir="rtl">
      {/* ── Hero ─────────────────────────────────────── */}
      <section className="relative min-h-[70vh] flex flex-col items-center justify-center px-4 py-20">
        {/* Background glow */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
                          w-[600px] h-[600px] bg-accent/5 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 text-center max-w-3xl mx-auto">
          {/* Gold line */}
          <div className="w-12 h-[3px] bg-gradient-to-l from-accent to-transparent mx-auto mb-8 rounded" />

          <h1 className="font-arabic text-4xl md:text-5xl lg:text-6xl font-bold text-primary mb-4 leading-tight">
            بحث في الشعر العربي
          </h1>
          <p className="text-secondary text-lg md:text-xl mb-10 font-arabic">
            ابحث بالبيت، بالمعنى، أو بالشاعر — واكتشف روائع الشعر العربي
          </p>

          {/* Search bar */}
          <div className="max-w-2xl mx-auto">
            <SearchBar
              placeholder="أدخل بيتاً من الشعر، اسم شاعر، أو وصفاً للمعنى..."
              size="lg"
            />
          </div>

          {/* Search mode hints */}
          <div className="flex justify-center gap-4 mt-4 flex-wrap">
            {[
              { label: "بيت شعري", example: "على قدر أهل العزم" },
              { label: "معنى", example: "شعر عن الشوق والغياب" },
              { label: "شاعر", example: "المتنبي" },
            ].map(({ label, example }) => (
              <Link
                key={label}
                href={`/search?q=${encodeURIComponent(example)}&mode=hybrid`}
                className="text-sm text-muted hover:text-accent transition-colors duration-200
                           border border-border rounded-full px-3 py-1 hover:border-accent/40
                           font-arabic"
              >
                {label}: &quot;{example}&quot;
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Featured Verses ───────────────────────────── */}
      <section className="px-4 py-16 max-w-5xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="accent-line mb-3" />
            <h2 className="font-arabic text-2xl font-bold text-primary">أبيات مختارة</h2>
          </div>
          <Link
            href="/search?mode=hybrid&is_famous=true"
            className="text-accent hover:text-accent-light text-sm transition-colors font-arabic"
          >
            عرض المزيد ←
          </Link>
        </div>

        <div className="space-y-3">
          {verses.map((verse: any) => (
            <VerseCard key={verse.id} verse={verse} />
          ))}
        </div>
      </section>

      {/* ── Categories ────────────────────────────────── */}
      <section className="px-4 py-16 bg-surface/30">
        <div className="max-w-5xl mx-auto">
          <div className="mb-8">
            <div className="accent-line mb-3" />
            <h2 className="font-arabic text-2xl font-bold text-primary">تصفح حسب الموضوع</h2>
          </div>
          <CategoryGrid categories={categories} />
        </div>
      </section>

      {/* ── Poets ─────────────────────────────────────── */}
      <section className="px-4 py-16 max-w-5xl mx-auto w-full">
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="accent-line mb-3" />
            <h2 className="font-arabic text-2xl font-bold text-primary">الشعراء البارزون</h2>
          </div>
          <Link
            href="/poets"
            className="text-accent hover:text-accent-light text-sm transition-colors font-arabic"
          >
            جميع الشعراء ←
          </Link>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {poets.map((poet: any) => (
            <PoetCard key={poet.id} poet={poet} />
          ))}
        </div>
      </section>
    </div>
  );
}

// ── Fallback data (shown if API is down) ──────────────
const FALLBACK_VERSES = [
  {
    id: "1",
    full_verse: "على قَدرِ أهلِ العزمِ تأتي العزائمُ *** وتأتي على قَدرِ الكِرامِ المكارمُ",
    poet_name_ar: "المتنبي",
    poem_title_ar: "على قدر أهل العزم",
    poem_slug: "almutanabbi-ala-qadri-ahlil-azm",
    is_famous: true,
  },
];

const FALLBACK_POETS = [
  { id: "1", name_ar: "المتنبي", slug: "almutanabbi", era: "abbasid", poem_count: 0, verse_count: 0 },
  { id: "2", name_ar: "نزار قباني", slug: "nizarqabbani", era: "contemporary", poem_count: 0, verse_count: 0 },
];

const FALLBACK_CATEGORIES = [
  { id: "1", name_ar: "الغزل والحب", slug: "love", icon: "❤️", color: "#E74C3C" },
  { id: "2", name_ar: "الحكمة", slug: "wisdom", icon: "🌙", color: "#8E44AD" },
  { id: "3", name_ar: "الفخر", slug: "pride", icon: "⚔️", color: "#E67E22" },
  { id: "4", name_ar: "الرثاء", slug: "elegy", icon: "🕊️", color: "#95A5A6" },
];
