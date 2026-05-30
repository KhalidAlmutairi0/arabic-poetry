"use client";

import Link from "next/link";
import { Share2, Star } from "lucide-react";
import { cn } from "@/lib/utils/cn";

function sanitizeHtml(html: string): string {
  return html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
    .replace(/&lt;mark&gt;/g, "<mark>")
    .replace(/&lt;\/mark&gt;/g, "</mark>");
}

interface Verse {
  id: string;
  full_verse: string;
  hemistich_1?: string;
  hemistich_2?: string;
  poet_name_ar?: string;
  poem_title_ar?: string;
  poem_slug?: string;
  poet_id?: string;
  is_famous?: boolean;
  _highlighted?: string;
}

interface VerseCardProps {
  verse: Verse;
  className?: string;
  showPoet?: boolean;
}

export function VerseCard({ verse, className, showPoet = true }: VerseCardProps) {
  const hasHemistiches = verse.hemistich_1 && verse.hemistich_2;
  const needsHighlight = !!verse._highlighted;

  return (
    <div
      className={cn(
        "card p-5 md:p-6 group cursor-pointer transition-all duration-200",
        "hover:bg-surface-elevated",
        verse.is_famous && "border-accent/20",
        className
      )}
    >
      <Link href={`/verses/${verse.id}`} className="block">
        {/* Famous badge */}
        {verse.is_famous && (
          <div className="flex justify-end mb-3">
            <span className="flex items-center gap-1 text-xs text-accent bg-accent/10 px-2 py-0.5 rounded-full font-arabic">
              <Star size={10} fill="currentColor" />
              بيت مشهور
            </span>
          </div>
        )}

        {/* Verse text */}
        <div className="verse-text text-center" dir="rtl">
          {hasHemistiches ? (
            <div className="flex justify-center items-baseline gap-4 md:gap-8 flex-wrap">
              <span className="block md:inline">{verse.hemistich_1}</span>
              <span className="text-accent-dim opacity-40 hidden md:inline text-sm">◈</span>
              <span className="block md:inline">{verse.hemistich_2}</span>
            </div>
          ) : needsHighlight ? (
            <span
              dangerouslySetInnerHTML={{
                __html: sanitizeHtml(verse._highlighted || ""),
              }}
            />
          ) : (
            <span>{verse.full_verse}</span>
          )}
        </div>
      </Link>

      {/* Footer */}
      {showPoet && (verse.poet_name_ar || verse.poem_title_ar) && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-border/50">
          <div className="font-arabic text-sm text-muted" dir="rtl">
            {verse.poet_name_ar && (
              <span className="text-secondary">— {verse.poet_name_ar}</span>
            )}
            {verse.poem_title_ar && (
              <span className="text-muted mr-2 text-xs">
                من قصيدة &quot;{verse.poem_title_ar}&quot;
              </span>
            )}
          </div>

          {/* Quick share */}
          <button
            onClick={(e) => {
              e.preventDefault();
              if (navigator.share) {
                navigator.share({
                  text: verse.full_verse,
                  url: `${window.location.origin}/verses/${verse.id}`,
                });
              } else {
                navigator.clipboard.writeText(verse.full_verse);
              }
            }}
            className="p-1.5 text-muted hover:text-accent transition-colors rounded-md
                       hover:bg-accent/10 opacity-0 group-hover:opacity-100"
            title="مشاركة"
          >
            <Share2 size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
