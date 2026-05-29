"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, Suspense } from "react";
import { SearchBar } from "@/components/search/SearchBar";
import { VerseCard } from "@/components/poetry/VerseCard";
import { useSearch } from "@/lib/hooks/useSearch";
import { Loader2, SearchX } from "lucide-react";

function SearchResults() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") || "";
  const initialMode = (searchParams.get("mode") as any) || "hybrid";

  const { query, setQuery, mode, setMode, results, isLoading, error } = useSearch();

  // Sync URL params on mount
  useEffect(() => {
    if (initialQ) setQuery(initialQ);
    if (initialMode) setMode(initialMode);
  }, []); // eslint-disable-line

  return (
    <div className="max-w-4xl mx-auto px-4 py-10" dir="rtl">
      {/* Search header */}
      <div className="mb-8">
        <h1 className="font-arabic text-2xl font-bold text-primary mb-6">بحث الشعر</h1>
        <SearchBar
          defaultValue={query}
          onSearch={(q, m) => { setQuery(q); setMode(m as any); }}
          placeholder="ابحث في الشعر العربي..."
        />
      </div>

      {/* Results summary */}
      {results && !isLoading && (
        <div className="mb-6 flex items-center justify-between">
          <p className="text-secondary text-sm font-arabic">
            {results.estimated_total_hits > 0
              ? `${results.estimated_total_hits.toLocaleString("ar-SA")} نتيجة`
              : "لا نتائج"}
            {query && <span className="text-muted mr-1">لـ &quot;{query}&quot;</span>}
          </p>
          <div className="flex items-center gap-2 text-xs text-muted">
            <span className="font-arabic">
              {mode === "hybrid" ? "بحث ذكي" : mode === "semantic" ? "بحث معنوي" : "بحث نصي"}
            </span>
            <span>·</span>
            <span>{results.processing_time_ms}ms</span>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex justify-center items-center py-20">
          <Loader2 className="animate-spin text-accent" size={32} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-center py-16">
          <p className="text-secondary font-arabic">{error}</p>
        </div>
      )}

      {/* No results */}
      {results && results.hits?.length === 0 && !isLoading && (
        <div className="text-center py-20">
          <SearchX className="mx-auto text-muted mb-4" size={48} />
          <p className="font-arabic text-lg text-secondary mb-2">لا توجد نتائج</p>
          <p className="text-muted text-sm font-arabic">
            جرّب البحث بكلمات مختلفة أو استخدم وضع البحث المعنوي
          </p>
        </div>
      )}

      {/* Results */}
      {results?.hits?.length > 0 && !isLoading && (
        <div className="space-y-3">
          {results.hits.map((hit: any) => (
            <VerseCard key={hit.id} verse={hit} />
          ))}
        </div>
      )}

      {/* Empty state (no search yet) */}
      {!query && !isLoading && !results && (
        <div className="text-center py-20">
          <div className="text-4xl mb-4">✦</div>
          <p className="font-arabic text-secondary text-lg">ابدأ البحث في روائع الشعر العربي</p>
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-xl mx-auto">
            {[
              "على قدر أهل العزم تأتي العزائم",
              "شعر عن الوطن والحنين",
              "أبيات في الحكمة والزمان",
            ].map((example) => (
              <button
                key={example}
                onClick={() => setQuery(example)}
                className="text-xs text-muted hover:text-accent transition-colors border border-border
                           hover:border-accent/40 rounded-lg px-3 py-2 font-arabic text-right"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={
      <div className="flex justify-center py-20">
        <Loader2 className="animate-spin text-accent" size={32} />
      </div>
    }>
      <SearchResults />
    </Suspense>
  );
}
