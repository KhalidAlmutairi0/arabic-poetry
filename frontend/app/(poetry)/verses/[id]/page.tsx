import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getVerse } from "@/lib/api/client";
import { ExplanationPanel } from "@/components/poetry/ExplanationPanel";
import { VerseCard } from "@/components/poetry/VerseCard";
import { ShareButton } from "@/components/poetry/ShareButton";
import { ChevronLeft, BookOpen } from "lucide-react";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  try {
    const verse = await getVerse(id);
    const simpleExplanation = verse.explanations?.find((e: any) => e.type === "simple");
    return {
      title: `${verse.full_verse.slice(0, 60)}... — ${verse.poet_name_ar}`,
      description:
        simpleExplanation?.explanation_ar?.slice(0, 160) ||
        `بيت شعري للشاعر ${verse.poet_name_ar} من قصيدة ${verse.poem_title_ar}`,
      openGraph: {
        title: verse.full_verse,
        description: `— ${verse.poet_name_ar}`,
      },
      alternates: { canonical: `/verses/${id}` },
    };
  } catch {
    return { title: "بيت شعري | شعر" };
  }
}

export default async function VersePage({ params }: Props) {
  const { id } = await params;

  let verse: any;
  try {
    verse = await getVerse(id);
  } catch {
    notFound();
  }

  const preloadedExplanation = verse.explanations?.find(
    (e: any) => e.type === "simple"
  )?.explanation_ar;

  return (
    <div className="max-w-3xl mx-auto px-4 py-10" dir="rtl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted mb-8 font-arabic flex-wrap">
        <Link href="/" className="hover:text-accent transition-colors">الرئيسية</Link>
        <ChevronLeft size={14} className="rotate-180" />
        {verse.poem_slug && (
          <>
            <Link href={`/poems/${verse.poem_slug}`} className="hover:text-accent transition-colors line-clamp-1 max-w-xs">
              {verse.poem_title_ar}
            </Link>
            <ChevronLeft size={14} className="rotate-180" />
          </>
        )}
        <span className="text-muted">بيت رقم {verse.position}</span>
      </nav>

      {/* ── Verse Display ── */}
      <section className="mb-12">
        <div className="accent-line mb-6" />

        {/* The verse — center stage */}
        <div className="text-center py-10 px-4">
          <p className="verse-text text-2xl md:text-3xl leading-loose">
            {verse.hemistich_1 && verse.hemistich_2 ? (
              <>
                {verse.hemistich_1}
                <span className="text-accent-dim opacity-30 mx-6">◈</span>
                {verse.hemistich_2}
              </>
            ) : (
              verse.full_verse
            )}
          </p>
        </div>

        {/* Attribution */}
        <div className="flex items-center justify-between mt-6">
          <div className="font-arabic text-sm text-secondary">
            {verse.poet_name_ar && (
              <Link
                href={`/poets/${verse.poet_id}`}
                className="text-accent hover:text-accent-light transition-colors font-semibold"
              >
                — {verse.poet_name_ar}
              </Link>
            )}
            {verse.poem_title_ar && (
              <Link
                href={`/poems/${verse.poem_slug}`}
                className="text-muted text-xs mr-3 hover:text-secondary transition-colors"
              >
                من قصيدة &quot;{verse.poem_title_ar}&quot;
              </Link>
            )}
          </div>

          <ShareButton text={verse.full_verse} />
        </div>
      </section>

      {/* ── AI Explanation ── */}
      <section className="mb-12">
        <div className="card p-6 md:p-8">
          <h2 className="font-arabic text-lg font-bold text-primary mb-6 flex items-center gap-2">
            <span className="text-accent">✨</span>
            شرح البيت
          </h2>
          <ExplanationPanel verseId={verse.id} preloaded={preloadedExplanation} />
        </div>
      </section>

      {/* ── Read Full Poem ── */}
      {verse.poem_slug && (
        <section className="mb-12">
          <Link
            href={`/poems/${verse.poem_slug}`}
            className="flex items-center justify-between p-5 card hover:bg-surface-elevated
                       transition-all group font-arabic"
          >
            <div>
              <p className="text-sm text-muted mb-1">قرأت هذا البيت؟</p>
              <p className="font-bold text-primary group-hover:text-accent transition-colors">
                اقرأ القصيدة كاملة
              </p>
              {verse.poem_title_ar && (
                <p className="text-xs text-muted mt-1">{verse.poem_title_ar}</p>
              )}
            </div>
            <BookOpen className="text-muted group-hover:text-accent transition-colors shrink-0" size={24} />
          </Link>
        </section>
      )}

      {/* ── Related Verses ── */}
      {verse.related_verses?.length > 0 && (
        <section>
          <h2 className="font-arabic text-xl font-bold text-primary mb-6">
            أبيات مشابهة
          </h2>
          <div className="space-y-3">
            {verse.related_verses.map((related: any) => (
              <VerseCard key={related.id} verse={related} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
