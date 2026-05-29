"use client";

import { useState } from "react";
import Link from "next/link";
import { ExplanationPanel } from "./ExplanationPanel";
import { Share2, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const ERA_LABELS: Record<string, string> = {
  pre_islamic: "الجاهلية", umayyad: "الأموي", abbasid: "العباسي",
  modern: "الحديث", contemporary: "المعاصر", andalusian: "الأندلسي",
};

interface PoemReaderProps {
  poem: any;
  verses: any[];
}

export function PoemReader({ poem, verses }: PoemReaderProps) {
  return (
    <article dir="rtl">
      {/* ── Poem Header ── */}
      <header className="mb-12">
        <div className="accent-line mb-4" />
        <h1 className="font-arabic text-3xl md:text-4xl font-bold text-primary mb-4 leading-tight">
          {poem.title_ar}
        </h1>

        <div className="flex flex-wrap items-center gap-3 text-sm font-arabic text-secondary">
          <Link
            href={`/poets/${poem.poet?.slug}`}
            className="text-accent hover:text-accent-light transition-colors font-semibold"
          >
            {poem.poet?.name_ar}
          </Link>

          {poem.era && (
            <>
              <span className="text-border">·</span>
              <span className="text-muted">{ERA_LABELS[poem.era] || poem.era}</span>
            </>
          )}

          {poem.meter && (
            <>
              <span className="text-border">·</span>
              <span className="text-muted">بحر {poem.meter}</span>
            </>
          )}

          {poem.verse_count > 0 && (
            <>
              <span className="text-border">·</span>
              <span className="text-muted">{poem.verse_count} بيتاً</span>
            </>
          )}
        </div>

        {/* Categories */}
        {poem.categories?.length > 0 && (
          <div className="flex gap-2 mt-4 flex-wrap">
            {poem.categories.map((cat: any) => (
              <Link
                key={cat.id}
                href={`/categories/${cat.slug}`}
                className="text-xs px-3 py-1 rounded-full border border-border text-muted
                           hover:border-accent/40 hover:text-accent transition-colors font-arabic"
              >
                {cat.name_ar}
              </Link>
            ))}
          </div>
        )}
      </header>

      {/* ── Verses ── */}
      <div className="space-y-1">
        {verses.map((verse, index) => (
          <VerseRow key={verse.id} verse={verse} index={index} />
        ))}
      </div>
    </article>
  );
}

function VerseRow({ verse, index }: { verse: any; index: number }) {
  const [expanded, setExpanded] = useState(false);

  const hasHemistiches = verse.hemistich_1 && verse.hemistich_2;

  return (
    <div className={cn(
      "group rounded-xl transition-colors",
      verse.is_famous && "border-r-2 border-accent/40 pr-4"
    )}>
      {/* Verse text row */}
      <div
        className="flex justify-between items-center gap-4 py-4 px-4 rounded-xl
                   hover:bg-surface/60 cursor-pointer transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        {hasHemistiches ? (
          <>
            <span className="verse-text flex-1 text-right">{verse.hemistich_1}</span>
            <span className="text-accent-dim opacity-30 shrink-0 hidden md:block">◈</span>
            <span className="verse-text flex-1 text-right">{verse.hemistich_2}</span>
          </>
        ) : (
          <span className="verse-text w-full text-center">{verse.full_verse}</span>
        )}

        {/* Actions (shown on hover) */}
        <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          <Link
            href={`/verses/${verse.id}`}
            onClick={(e) => e.stopPropagation()}
            className="p-1.5 text-muted hover:text-accent transition-colors rounded"
            title="فتح البيت"
          >
            <ExternalLink size={13} />
          </Link>
          <button
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard?.writeText(verse.full_verse);
            }}
            className="p-1.5 text-muted hover:text-accent transition-colors rounded"
            title="نسخ"
          >
            <Share2 size={13} />
          </button>
        </div>
      </div>

      {/* Expandable explanation */}
      {expanded && (
        <div
          className="border-r-2 border-accent/30 mr-6 pr-4 pb-4 mb-2 animate-slide-down"
          onClick={(e) => e.stopPropagation()}
        >
          <ExplanationPanel verseId={verse.id} />
        </div>
      )}
    </div>
  );
}
