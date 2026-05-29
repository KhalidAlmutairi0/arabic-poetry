"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, X, Loader2 } from "lucide-react";
import { autocomplete } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";

interface SearchBarProps {
  placeholder?: string;
  defaultValue?: string;
  size?: "default" | "lg";
  onSearch?: (q: string, mode: string) => void;
  className?: string;
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debouncedValue;
}

export function SearchBar({
  placeholder = "ابحث في الشعر العربي...",
  defaultValue = "",
  size = "default",
  onSearch,
  className,
}: SearchBarProps) {
  const router = useRouter();
  const [query, setQuery] = useState(defaultValue);
  const [mode, setMode] = useState<"hybrid" | "keyword" | "semantic">("hybrid");
  const [suggestions, setSuggestions] = useState<any>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounce(query, 300);

  // Fetch autocomplete suggestions
  useEffect(() => {
    if (debouncedQuery.length < 2) {
      setSuggestions(null);
      return;
    }
    setIsLoading(true);
    autocomplete(debouncedQuery)
      .then(setSuggestions)
      .catch(() => setSuggestions(null))
      .finally(() => setIsLoading(false));
  }, [debouncedQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSubmit = useCallback(
    (q: string = query) => {
      if (!q.trim()) return;
      setShowSuggestions(false);
      if (onSearch) {
        onSearch(q, mode);
      } else {
        router.push(`/search?q=${encodeURIComponent(q)}&mode=${mode}`);
      }
    },
    [query, mode, onSearch, router]
  );

  const hasSuggestions =
    suggestions &&
    ((suggestions.verses?.length > 0) ||
     (suggestions.poets?.length > 0));

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      {/* Input */}
      <div className="relative">
        <Search
          className="absolute right-4 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
          size={size === "lg" ? 20 : 18}
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowSuggestions(true);
          }}
          onFocus={() => setShowSuggestions(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
            if (e.key === "Escape") setShowSuggestions(false);
          }}
          placeholder={placeholder}
          dir="rtl"
          className={cn(
            "search-input",
            size === "lg" && "text-xl py-5 px-6 pr-14",
            size === "default" && "py-3 pr-12"
          )}
        />
        {query && (
          <button
            onClick={() => { setQuery(""); setSuggestions(null); inputRef.current?.focus(); }}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-muted hover:text-primary transition-colors"
          >
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : <X size={16} />}
          </button>
        )}
      </div>

      {/* Mode selector */}
      <div className="flex gap-2 mt-2 justify-end" dir="rtl">
        {([
          { value: "hybrid",   label: "ذكي" },
          { value: "keyword",  label: "نص" },
          { value: "semantic", label: "معنى" },
        ] as const).map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setMode(value)}
            className={cn(
              "text-xs px-3 py-1 rounded-full transition-all border font-arabic",
              mode === value
                ? "bg-accent text-background border-accent font-semibold"
                : "text-muted border-border hover:border-accent/50 hover:text-secondary"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && hasSuggestions && (
        <div
          className="absolute top-full left-0 right-0 mt-2 bg-surface-elevated border border-border
                     rounded-xl shadow-2xl z-50 overflow-hidden animate-slide-down"
          dir="rtl"
        >
          {/* Verse suggestions */}
          {suggestions.verses?.length > 0 && (
            <div>
              <div className="px-4 py-2 text-xs text-muted border-b border-border">
                أبيات مقترحة
              </div>
              {suggestions.verses.map((s: any) => (
                <button
                  key={s.id}
                  onClick={() => { setQuery(s.full_verse); handleSubmit(s.full_verse); }}
                  className="w-full text-right px-4 py-3 hover:bg-surface-hover transition-colors
                             border-b border-border/50 last:border-0"
                >
                  <p className="font-arabic text-sm text-primary line-clamp-1">{s.full_verse}</p>
                  {s.poet_name_ar && (
                    <p className="text-xs text-muted mt-0.5">— {s.poet_name_ar}</p>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* Poet suggestions */}
          {suggestions.poets?.length > 0 && (
            <div className="border-t border-border">
              <div className="px-4 py-2 text-xs text-muted border-b border-border">شعراء</div>
              {suggestions.poets.map((p: any) => (
                <button
                  key={p.slug}
                  onClick={() => router.push(`/poets/${p.slug}`)}
                  className="w-full text-right px-4 py-3 hover:bg-surface-hover transition-colors
                             flex items-center gap-3"
                >
                  <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center
                                  text-accent text-xs font-arabic shrink-0">
                    {p.name_ar.charAt(0)}
                  </div>
                  <span className="font-arabic text-sm text-primary">{p.name_ar}</span>
                </button>
              ))}
            </div>
          )}

          {/* Search action */}
          <div className="px-4 py-3 bg-surface border-t border-border">
            <button
              onClick={() => handleSubmit()}
              className="w-full btn-primary py-2 text-sm font-arabic"
            >
              بحث عن &quot;{query}&quot;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
