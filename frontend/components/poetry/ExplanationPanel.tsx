"use client";

import { useState } from "react";
import { Sparkles, RefreshCw } from "lucide-react";
import { useExplanation, type ExplanationType } from "@/lib/hooks/useExplanation";
import { cn } from "@/lib/utils/cn";

interface ExplanationPanelProps {
  verseId: string;
  preloaded?: string;
}

const TABS: { value: ExplanationType; label: string }[] = [
  { value: "simple",    label: "تبسيط" },
  { value: "literary",  label: "تحليل أدبي" },
  { value: "linguistic", label: "تحليل لغوي" },
];

export function ExplanationPanel({ verseId, preloaded }: ExplanationPanelProps) {
  const [activeType, setActiveType] = useState<ExplanationType>("simple");
  const { explanation, isLoading, isComplete, error, source, start, reset } =
    useExplanation(verseId, activeType);

  const hasContent = explanation || preloaded;
  const displayText = explanation || preloaded || "";

  const handleTypeChange = (type: ExplanationType) => {
    setActiveType(type);
    reset();
  };

  return (
    <div className="space-y-4" dir="rtl">
      {/* Type tabs */}
      <div className="flex gap-2 flex-wrap">
        {TABS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => handleTypeChange(value)}
            className={cn(
              "text-xs px-3 py-1.5 rounded-full transition-all border font-arabic",
              activeType === value
                ? "bg-accent/15 text-accent border-accent/40 font-semibold"
                : "text-muted border-border hover:border-border-strong hover:text-secondary"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      {!hasContent && !isLoading && !error && (
        <button
          onClick={start}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                     border border-accent/30 text-accent hover:bg-accent/10 transition-all
                     font-arabic text-sm group"
        >
          <Sparkles size={16} className="group-hover:animate-pulse-soft" />
          اشرح هذا البيت بالذكاء الاصطناعي
        </button>
      )}

      {error && (
        <div className="text-sm text-red-400/80 bg-red-500/10 rounded-lg p-3 font-arabic">
          {error}
          <button onClick={start} className="mr-3 text-accent hover:underline">
            إعادة المحاولة
          </button>
        </div>
      )}

      {(hasContent || isLoading) && (
        <div className="space-y-3">
          {/* Source badge */}
          {isComplete && source && (
            <div className="flex justify-end">
              <span className="text-xs text-muted bg-surface px-2 py-0.5 rounded-full border border-border font-arabic">
                {source === "ai" ? "✨ توليد ذكاء اصطناعي" :
                 source === "cache" ? "⚡ محفوظ" : "📚 من قاعدة البيانات"}
              </span>
            </div>
          )}

          {/* Explanation text */}
          <div
            className={cn(
              "font-arabic text-sm leading-loose text-secondary",
              isLoading && !isComplete && "streaming-cursor"
            )}
          >
            {displayText}
          </div>

          {/* Regenerate */}
          {isComplete && (
            <button
              onClick={() => { reset(); start(); }}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-accent
                         transition-colors font-arabic mt-2"
            >
              <RefreshCw size={12} />
              توليد شرح آخر
            </button>
          )}
        </div>
      )}
    </div>
  );
}
