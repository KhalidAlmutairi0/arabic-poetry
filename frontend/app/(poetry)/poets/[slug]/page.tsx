import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPoet, getPoetPoems } from "@/lib/api/client";
import { VerseCard } from "@/components/poetry/VerseCard";
import { BookOpen, Calendar, MapPin, ChevronLeft } from "lucide-react";

interface Props {
  params: Promise<{ slug: string }>;
}

const ERA_LABELS: Record<string, string> = {
  pre_islamic: "الجاهلية", umayyad: "الأموي", abbasid: "العباسي",
  modern: "الحديث", contemporary: "المعاصر", andalusian: "الأندلسي",
  mamluk: "المملوكي", ottoman: "العثماني", islamic_early: "صدر الإسلام",
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const poet = await getPoet(slug);
    return {
      title: poet.name_ar,
      description: poet.bio_ar?.slice(0, 160) || `شاعر عربي — ${poet.name_ar}`,
      openGraph: {
        title: `${poet.name_ar} | شعر`,
        description: poet.bio_ar?.slice(0, 160),
      },
    };
  } catch {
    return { title: "شاعر | شعر" };
  }
}

export default async function PoetPage({ params }: Props) {
  const { slug } = await params;

  let poet: any;
  let poems: any;

  try {
    [poet, poems] = await Promise.all([
      getPoet(slug),
      getPoetPoems(slug),
    ]);
  } catch {
    notFound();
  }

  const eraLabel = poet.era ? ERA_LABELS[poet.era] || poet.era : null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-10" dir="rtl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted mb-8 font-arabic">
        <Link href="/" className="hover:text-accent transition-colors">الرئيسية</Link>
        <ChevronLeft size={14} className="rotate-180" />
        <Link href="/poets" className="hover:text-accent transition-colors">الشعراء</Link>
        <ChevronLeft size={14} className="rotate-180" />
        <span className="text-secondary">{poet.name_ar}</span>
      </nav>

      {/* ── Poet Hero ── */}
      <header className="mb-12">
        <div className="flex gap-6 items-start">
          {/* Avatar */}
          <div className="w-20 h-20 md:w-24 md:h-24 shrink-0 rounded-full bg-gradient-to-br
                          from-accent/30 to-accent/5 border border-accent/20
                          flex items-center justify-center">
            {poet.image_url ? (
              <img src={poet.image_url} alt={poet.name_ar}
                   className="w-full h-full rounded-full object-cover" />
            ) : (
              <span className="font-arabic text-3xl text-accent">{poet.name_ar.charAt(0)}</span>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="accent-line mb-3" />
            <h1 className="font-arabic text-3xl md:text-4xl font-bold text-primary mb-2">
              {poet.name_ar}
            </h1>
            {poet.name_en && (
              <p className="text-secondary text-sm mb-3" dir="ltr">{poet.name_en}</p>
            )}

            {/* Metadata badges */}
            <div className="flex flex-wrap gap-3 text-xs text-muted font-arabic">
              {eraLabel && (
                <span className="flex items-center gap-1 bg-surface px-2.5 py-1 rounded-full border border-border">
                  <Calendar size={11} />
                  {eraLabel}
                </span>
              )}
              {poet.birth_place_ar && (
                <span className="flex items-center gap-1 bg-surface px-2.5 py-1 rounded-full border border-border">
                  <MapPin size={11} />
                  {poet.birth_place_ar}
                </span>
              )}
              {poet.birth_year && (
                <span className="bg-surface px-2.5 py-1 rounded-full border border-border">
                  {poet.birth_year} — {poet.death_year || "؟"}م
                </span>
              )}
              <span className="flex items-center gap-1 bg-surface px-2.5 py-1 rounded-full border border-border">
                <BookOpen size={11} />
                {poet.poem_count} قصيدة
              </span>
            </div>
          </div>
        </div>

        {/* Bio */}
        {poet.bio_ar && (
          <div className="mt-8 p-6 card">
            <p className="font-arabic text-secondary leading-relaxed text-sm md:text-base">
              {poet.bio_ar}
            </p>
          </div>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* ── Poems list ── */}
        <div className="lg:col-span-2">
          <h2 className="font-arabic text-xl font-bold text-primary mb-6">قصائده</h2>
          <div className="space-y-3">
            {poems?.poems?.map((poem: any) => (
              <Link key={poem.id} href={`/poems/${poem.slug}`}>
                <div className="card p-4 hover:bg-surface-elevated transition-all group font-arabic">
                  <div className="flex justify-between items-start gap-4">
                    <h3 className="text-primary font-semibold group-hover:text-accent transition-colors">
                      {poem.title_ar}
                    </h3>
                    <span className="text-xs text-muted shrink-0">{poem.verse_count} بيتاً</span>
                  </div>
                  {poem.meter && (
                    <p className="text-xs text-muted mt-1">بحر {poem.meter}</p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* ── Famous verses sidebar ── */}
        <div>
          <h2 className="font-arabic text-xl font-bold text-primary mb-6">أشهر أبياته</h2>
          <div className="space-y-3">
            {poet.famous_verses?.map((verse: any) => (
              <VerseCard key={verse.id} verse={verse} showPoet={false} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
