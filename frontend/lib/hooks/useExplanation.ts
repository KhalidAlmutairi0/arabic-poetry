"use client";

import { useState, useCallback, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ExplanationType = "simple" | "literary" | "linguistic";

export function useExplanation(verseId: string, type: ExplanationType) {
  const [explanation, setExplanation] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"ai" | "cache" | "db" | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    // Cancel any existing request
    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;

    setExplanation("");
    setIsLoading(true);
    setIsComplete(false);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/v1/ai/verses/${verseId}/explain?type=${type}`,
        {
          signal: controller.signal,
          headers: { Accept: "text/event-stream" },
        }
      );

      if (!response.ok || !response.body) {
        throw new Error("فشل الاتصال بالخدمة");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6);

          try {
            const parsed = JSON.parse(data);
            if (parsed.done) {
              setIsComplete(true);
              setSource(parsed.source || "ai");
              setIsLoading(false);
            } else if (parsed.text) {
              setExplanation((prev) => prev + parsed.text);
            } else if (parsed.error) {
              setError(parsed.error);
              setIsLoading(false);
            }
          } catch {
            // Ignore parse errors for incomplete chunks
          }
        }
      }
    } catch (err: any) {
      if (err.name !== "AbortError") {
        setError("حدث خطأ أثناء توليد الشرح");
        setIsLoading(false);
      }
    }
  }, [verseId, type]);

  const reset = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    setExplanation("");
    setIsLoading(false);
    setIsComplete(false);
    setError(null);
    setSource(null);
  }, []);

  return { explanation, isLoading, isComplete, error, source, start, reset };
}
