import { MetadataRoute } from "next";
import { api } from "@/lib/api/client";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const revalidate = 86400; // Regenerate daily

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: new Date(), changeFrequency: "daily", priority: 1.0 },
    { url: `${BASE_URL}/poets`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE_URL}/poems`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${BASE_URL}/categories`, changeFrequency: "monthly", priority: 0.8 },
  ];

  try {
    const [poetsData, poemsData] = await Promise.allSettled([
      api.get<{ slugs: string[] }>("/api/v1/poets/slugs"),
      api.get<{ slugs: string[] }>("/api/v1/poems/slugs"),
    ]);

    const poetPages: MetadataRoute.Sitemap =
      poetsData.status === "fulfilled"
        ? (poetsData.value.slugs || []).map((slug) => ({
            url: `${BASE_URL}/poets/${slug}`,
            changeFrequency: "monthly" as const,
            priority: 0.8,
          }))
        : [];

    const poemPages: MetadataRoute.Sitemap =
      poemsData.status === "fulfilled"
        ? (poemsData.value.slugs || []).map((slug) => ({
            url: `${BASE_URL}/poems/${slug}`,
            changeFrequency: "monthly" as const,
            priority: 0.7,
          }))
        : [];

    return [...staticPages, ...poetPages, ...poemPages];
  } catch {
    return staticPages;
  }
}
