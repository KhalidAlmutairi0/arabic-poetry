"use client";

import { useState, useEffect, useCallback } from "react";
import { searchVerses } from "@/lib/api/client";

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debouncedValue;
}

export type SearchMode = "hybrid" | "keyword" | "semantic";

export interface SearchFilters {
  era?: string;
  poet_id?: string;
  is_famous?: boolean;
}

export function useSearch() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [filters, setFilters] = useState<SearchFilters>({});
  const [page, setPage] = useState(1);
  const [results, setResults] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debouncedQuery = useDebounce(query, 350);

  const doSearch = useCallback(
    async (q: string, currentMode: SearchMode, currentFilters: SearchFilters, currentPage: number) => {
      if (!q.trim()) {
        setResults(null);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await searchVerses({
          q,
          mode: currentMode,
          page: currentPage,
          limit: 20,
          ...currentFilters,
        });
        setResults(result);
      } catch (err: any) {
        setError(err.message || "حدث خطأ في البحث");
        setResults(null);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    doSearch(debouncedQuery, mode, filters, page);
  }, [debouncedQuery, mode, filters, page, doSearch]);

  const updateQuery = useCallback((q: string) => {
    setQuery(q);
    setPage(1); // Reset page on new query
  }, []);

  const updateMode = useCallback((m: SearchMode) => {
    setMode(m);
    setPage(1);
  }, []);

  return {
    query,
    setQuery: updateQuery,
    mode,
    setMode: updateMode,
    filters,
    setFilters,
    page,
    setPage,
    results,
    isLoading,
    error,
    hasResults: results?.hits?.length > 0,
  };
}
