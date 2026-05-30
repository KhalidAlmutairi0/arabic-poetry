import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api/client";
import { BookOpen, ChevronLeft } from "lucide-react";

interface Props {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

async function getCategory(slug: string) {
  try {
    return await api.get(`/api/v1/categories/${slug}`);
  } catch {
    return null;
  }
}

async function getCategoryPoems(slug: string, page: number) {
  try {
    return await api.get(`/api/v1/poems?category=${slug}&page=${page}&limit=20`);
  } catch {
    return { items: [], total: 0 };
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const category = await getCategory(slug);
  if (!category) return { title: "تصنيف | شعر" };
  return {
    title: category.name_ar,
    description: category.description_ar || `قصائد في ${category.name_ar}`,
  };
}

export default async function CategoryPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const { page: pageStr } = await searchParams;
  const page = parseInt(pageStr || "1", 10);

  const category = await getCategory(slug);
  if (!category) notFound();

  const data = await getCategoryPoems(slug, page);
  const poems = data.items || [];
  const total = data.total || 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="max-w-4xl mx-auto px-4 py-10" dir="rtl">
      <nav className="flex items-center gap-2 text-sm text-muted mb-8 font-arabic">
        <Link href="/" className="hover:text-accent transition-colors">الرئيسية</Link>
        <ChevronLeft size={14} className="rotate-180" />
        <Link href="/categories" className="hover:text-accent transition-colors">التصنيفات</Link>
        <ChevronLeft size={14} className="rotate-180" />
        <span className="text-secondary">{category.name_ar}</span>
      </nav>

      <div className="mb-8">
        <div className="accent-line mb-3" />
        <h1 className="font-arabic text-3xl font-bold text-primary">{category.name_ar}</h1>
        {category.description_ar && (
          <p className="text-muted text-sm font-arabic mt-2">{category.description_ar}</p>
        )}
        {total > 0 && (
          <p className="text-muted text-xs font-arabic mt-1">
            {total.toLocaleString("ar-SA")} قصيدة
          </p>
        )}
      </div>

      {poems.length > 0 ? (
        <div className="space-y-3">
          {poems.map((poem: any) => (
            <Link key={poem.id} href={`/poems/${poem.slug}`}>
              <div className="card p-5 hover:bg-surface-elevated transition-all group font-arabic">
                <div className="flex justify-between items-start gap-4">
                  <div className="min-w-0">
                    <h3 className="text-primary font-semibold group-hover:text-accent transition-colors text-lg">
                      {poem.title_ar}
                    </h3>
                    {poem.poet?.name_ar && (
                      <p className="text-sm text-secondary mt-1">— {poem.poet.name_ar}</p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-muted">
                      {poem.meter && <span>بحر {poem.meter}</span>}
                      {poem.verse_count > 0 && (
                        <span className="flex items-center gap-1">
                          <BookOpen size={11} />
                          {poem.verse_count} بيتاً
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <p className="font-arabic text-secondary text-lg">لا توجد قصائد في هذا التصنيف حالياً</p>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-10">
          {page > 1 && (
            <Link
              href={`/categories/${slug}?page=${page - 1}`}
              className="btn-ghost text-sm font-arabic"
            >
              السابق
            </Link>
          )}
          <span className="flex items-center px-4 text-sm text-muted font-arabic">
            {page} / {totalPages}
          </span>
          {page < totalPages && (
            <Link
              href={`/categories/${slug}?page=${page + 1}`}
              className="btn-ghost text-sm font-arabic"
            >
              التالي
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
