const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit & { next?: NextFetchRequestConfig } = {}
  ): Promise<T> {
    const { next, ...fetchOptions } = options;

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...fetchOptions,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...fetchOptions.headers,
      },
      next,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: "Request failed" }));
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async get<T = any>(path: string, cacheOptions?: NextFetchRequestConfig): Promise<T> {
    return this.request<T>(path, { method: "GET", next: cacheOptions });
  }

  async post<T = any>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }
}

// ── Type augmentation for Next.js fetch cache ──────────
interface NextFetchRequestConfig {
  revalidate?: number | false;
  tags?: string[];
}

export const api = new ApiClient(API_BASE);

// ── Typed API functions ────────────────────────────────

export async function searchVerses(params: {
  q: string;
  mode?: string;
  page?: number;
  limit?: number;
  poet_id?: string;
  era?: string;
  is_famous?: boolean;
}) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) qs.set(k, String(v));
  });
  return api.get(`/api/v1/search?${qs.toString()}`);
}

export async function getPoet(slug: string) {
  return api.get(`/api/v1/poets/${slug}`, {
    revalidate: 86400,
    tags: [`poet-${slug}`],
  });
}

export async function getPoetPoems(slug: string, page = 1) {
  return api.get(`/api/v1/poets/${slug}/poems?page=${page}`, {
    revalidate: 3600,
    tags: [`poet-poems-${slug}`],
  });
}

export async function getPoem(slug: string) {
  return api.get(`/api/v1/poems/${slug}`, {
    revalidate: 86400,
    tags: [`poem-${slug}`],
  });
}

export async function getVerse(id: string) {
  return api.get(`/api/v1/verses/${id}`, {
    revalidate: 86400,
    tags: [`verse-${id}`],
  });
}

export async function getCategories() {
  return api.get("/api/v1/categories", { revalidate: 86400 });
}

export async function getPoets(params?: { era?: string; page?: number; limit?: number }) {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) qs.set(k, String(v));
    });
  }
  const query = qs.toString();
  return api.get(`/api/v1/poets${query ? `?${query}` : ""}`, { revalidate: 3600 });
}

export async function getPoems(params?: { poet_id?: string; era?: string; meter?: string; page?: number; limit?: number }) {
  const qs = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) qs.set(k, String(v));
    });
  }
  const query = qs.toString();
  return api.get(`/api/v1/poems${query ? `?${query}` : ""}`, { revalidate: 3600 });
}

export async function getFamousVerses(limit = 5) {
  return api.get(`/api/v1/verses/famous?limit=${limit}`, { revalidate: 3600 });
}

export async function getRelatedVerses(verseId: string) {
  return api.get(`/api/v1/verses/${verseId}/related`, { revalidate: 3600 });
}

export async function autocomplete(q: string) {
  return api.get(`/api/v1/search/autocomplete?q=${encodeURIComponent(q)}`);
}
