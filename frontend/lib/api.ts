const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
const V1 = `${API_BASE}/api/v1`

export interface Poet {
  id: string
  name_ar: string
  name_en: string | null
  slug: string
  bio_ar: string | null
  era: string | null
  birth_year: number | null
  death_year: number | null
  birth_place_ar: string | null
  image_url: string | null
  poem_count: number
  verse_count: number
  is_verified: boolean
  famous_verses?: FamousVerseSnippet[]
}

export interface FamousVerseSnippet {
  id: string
  full_verse: string
  poem_title_ar: string | null
  poem_slug: string | null
}

export interface PoetsListResponse {
  items: Poet[]
  total: number
  page: number
  size: number
}

export interface PoetPoem {
  id: string
  title_ar: string
  slug: string
  verse_count: number
  meter: string | null
  view_count: number
}

export interface PoetPoemsResponse {
  poet_id: string
  poet_name_ar: string
  poems: PoetPoem[]
}

export interface Verse {
  id: string
  full_verse: string
  hemistich_1: string
  hemistich_2: string
  position: number
  is_famous: boolean
  poet_name_ar: string
  poem_title_ar: string
  poem_slug: string
  poet_id: string
  poem_id: string
  explanations: VerseExplanation[]
  related_verses: RelatedVerse[]
}

export interface VerseExplanation {
  id: string
  type: "simple" | "literary" | "linguistic"
  explanation_ar: string
  difficult_words: { word: string; meaning: string }[]
  is_ai_generated: boolean
  is_reviewed: boolean
}

export interface RelatedVerse {
  id: string
  full_verse: string
  hemistich_1: string
  hemistich_2: string
  poet_name_ar: string
  poem_title_ar: string
  poem_slug: string
  similarity: number
}

export interface PoemVerse {
  id: string
  position: number
  hemistich_1: string
  hemistich_2: string
  full_verse: string
  is_famous: boolean
}

export interface Poem {
  id: string
  title_ar: string
  title_en: string | null
  slug: string
  meter: string | null
  rhyme_char: string | null
  era: string | null
  is_verified: boolean
  view_count: number
  poet: {
    id: string
    name_ar: string
    slug: string
    era: string | null
  }
  categories: { id: string; name_ar: string; slug: string }[]
  verses: PoemVerse[]
}

export interface Category {
  id: string
  name_ar: string
  name_en: string | null
  slug: string
  icon: string | null
  color: string | null
  description_ar: string | null
  poem_count: number
}

export interface SearchHit {
  id: string
  hemistich_1: string
  hemistich_2: string
  full_verse: string
  poet_name_ar: string
  poem_title_ar: string
  poem_slug: string
  poet_slug: string
  is_famous: boolean
  era: string | null
  score?: number
  _formatted?: {
    hemistich_1?: string
    hemistich_2?: string
    full_verse?: string
    poet_name_ar?: string
  }
}

export interface SearchResponse {
  hits: SearchHit[]
  estimated_total_hits: number
  query: string
  mode: string
  processing_time_ms: number
  page: number
  total_pages: number
}

export interface AutocompleteResponse {
  verses: { id: string; full_verse: string; poet_name_ar: string }[]
  poets: { slug: string; name_ar: string; era: string | null }[]
}

async function apiFetch<T>(
  path: string,
  options?: RequestInit & { next?: NextFetchRequestConfig }
): Promise<T | null> {
  try {
    const res = await fetch(`${V1}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

export async function getPoets(params?: {
  era?: string
  page?: number
  limit?: number
}): Promise<PoetsListResponse | null> {
  const qs = new URLSearchParams()
  if (params?.era) qs.set("era", params.era)
  if (params?.page) qs.set("page", String(params.page))
  if (params?.limit) qs.set("limit", String(params.limit))
  const query = qs.toString() ? `?${qs}` : ""
  return apiFetch<PoetsListResponse>(`/poets/${query}`, {
    next: { revalidate: 3600, tags: ["poets"] },
  })
}

export async function getPoet(slug: string): Promise<Poet | null> {
  return apiFetch<Poet>(`/poets/${slug}`, {
    next: { revalidate: 86400, tags: [`poet-${slug}`] },
  })
}

export async function getPoetPoems(
  slug: string,
  page = 1,
  limit = 20
): Promise<PoetPoemsResponse | null> {
  return apiFetch<PoetPoemsResponse>(
    `/poets/${slug}/poems?page=${page}&limit=${limit}`,
    { next: { revalidate: 3600, tags: [`poet-poems-${slug}`] } }
  )
}

export async function getPoem(slug: string): Promise<Poem | null> {
  return apiFetch<Poem>(`/poems/${slug}`, {
    next: { revalidate: 86400, tags: [`poem-${slug}`] },
  })
}

export async function getVerse(id: string): Promise<Verse | null> {
  return apiFetch<Verse>(`/verses/${id}`, {
    next: { revalidate: 86400, tags: [`verse-${id}`] },
  })
}

export async function getRelatedVerses(
  verseId: string,
  limit = 6
): Promise<{ related: RelatedVerse[] } | null> {
  return apiFetch(`/verses/${verseId}/related?limit=${limit}`, {
    next: { revalidate: 3600 },
  })
}

export async function getTrendingVerses(limit = 5): Promise<SearchResponse | null> {
  return apiFetch<SearchResponse>(
    `/search/?q=*&is_famous=true&limit=${limit}&page=1`,
    { next: { revalidate: 1800, tags: ["trending"] } }
  )
}

export async function getFamousVerses(limit = 5): Promise<SearchResponse | null> {
  return apiFetch<SearchResponse>(
    `/search/?q=%D8%B4%D8%B9%D8%B1&is_famous=true&limit=${limit}&page=1`,
    { next: { revalidate: 3600, tags: ["famous"] } }
  )
}

export async function searchPoetry(params: {
  q: string
  mode?: "keyword" | "semantic" | "hybrid"
  era?: string
  poet_id?: string
  is_famous?: boolean
  page?: number
  limit?: number
}): Promise<SearchResponse | null> {
  const qs = new URLSearchParams({ q: params.q })
  if (params.mode) qs.set("mode", params.mode)
  if (params.era) qs.set("era", params.era)
  if (params.poet_id) qs.set("poet_id", params.poet_id)
  if (params.is_famous != null) qs.set("is_famous", String(params.is_famous))
  if (params.page) qs.set("page", String(params.page))
  if (params.limit) qs.set("limit", String(params.limit))
  return apiFetch<SearchResponse>(`/search/?${qs}`)
}

export async function autocomplete(q: string): Promise<AutocompleteResponse | null> {
  return apiFetch<AutocompleteResponse>(
    `/search/autocomplete?q=${encodeURIComponent(q)}`
  )
}

export async function getCategories(): Promise<Category[] | null> {
  return apiFetch<Category[]>("/categories/", {
    next: { revalidate: 86400, tags: ["categories"] },
  })
}

export function getExplanationStreamUrl(
  verseId: string,
  type: "simple" | "literary" | "linguistic" = "simple"
): string {
  return `${V1}/ai/verses/${verseId}/explain?type=${type}`
}

export const ERA_LABELS: Record<string, string> = {
  pre_islamic: "العصر الجاهلي",
  islamic: "العصر الإسلامي",
  umayyad: "العصر الأموي",
  abbasid: "العصر العباسي",
  andalusian: "العصر الأندلسي",
  mamluk: "العصر المملوكي",
  ottoman: "العصر العثماني",
  modern: "العصر الحديث",
  contemporary: "العصر المعاصر",
}

export function formatEra(era: string | null): string {
  if (!era) return "غير محدد"
  return ERA_LABELS[era] ?? era
}
