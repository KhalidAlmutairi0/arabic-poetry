import type { Metadata } from "next";
import Link from "next/link";
import { getPoems } from "@/lib/api/client";
import { BookOpen } from "lucide-react";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "القصائد",
  description: "تصفح مكتبة القصائد العربية — آلاف القصائد من مختلف العصور والبحور.",
};

interface Props {
  searchParams: Promise<{ era?: string; meter?: string; page?: string }>;
}

export default async function PoemsPage({ searchParams }: Props) {
  const { era, meter, page: pageStr } = await searchParams;
  const page = parseInt(pageStr || "1", 10);

  let data: any;
  try {
    data = await getPoems({ era, meter, page, limit: 20 });
  } catch {
    data = { items: [], total: 0, page: 1 };
  }

  const poems = data.items || [];
  const total = data.total || 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="max-w-4xl mx-auto px-4 py-10" dir="rtl">
      <div className="mb-8">
        <div className="accent-line mb-3" />
        <h1 className="font-arabic text-3xl font-bold text-primary">القصائد</h1>
        {total > 0 && (
          <p className="text-muted text-sm font-arabic mt-2">{total.toLocaleString("ar-SA")} قصيدة</p>
        )}
      </div>

      {/* Poems list */}
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
                  <span className="text-xs text-muted shrink-0">
                    {poem.view_count?.toLocaleString("ar-SA") || "0"} مشاهدة
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <p className="font-arabic text-secondary text-lg">لا توجد قصائد</p>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-10">
          {page > 1 && (
            <Link
              href={`/poems?${era ? `era=${era}&` : ""}${meter ? `meter=${meter}&` : ""}page=${page - 1}`}
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
              href={`/poems?${era ? `era=${era}&` : ""}${meter ? `meter=${meter}&` : ""}page=${page + 1}`}
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
