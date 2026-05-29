import type { Metadata } from "next";
import { getPoets } from "@/lib/api/client";
import { PoetCard } from "@/components/poetry/PoetCard";
import Link from "next/link";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "الشعراء",
  description: "تصفح شعراء العربية عبر العصور — من الجاهلية إلى العصر الحديث.",
};

const ERA_TABS = [
  { value: "",              label: "الكل" },
  { value: "pre_islamic",   label: "الجاهلية" },
  { value: "islamic_early", label: "صدر الإسلام" },
  { value: "umayyad",       label: "الأموي" },
  { value: "abbasid",       label: "العباسي" },
  { value: "andalusian",    label: "الأندلسي" },
  { value: "modern",        label: "الحديث" },
  { value: "contemporary",  label: "المعاصر" },
];

interface Props {
  searchParams: Promise<{ era?: string; page?: string }>;
}

export default async function PoetsPage({ searchParams }: Props) {
  const { era, page: pageStr } = await searchParams;
  const page = parseInt(pageStr || "1", 10);

  let data: any;
  try {
    data = await getPoets({ era, page, limit: 24 });
  } catch {
    data = { items: [], total: 0, page: 1, total_pages: 0 };
  }

  const poets = data.items || [];
  const totalPages = data.total_pages || Math.ceil((data.total || 0) / 24);

  return (
    <div className="max-w-5xl mx-auto px-4 py-10" dir="rtl">
      <div className="mb-8">
        <div className="accent-line mb-3" />
        <h1 className="font-arabic text-3xl font-bold text-primary">الشعراء</h1>
      </div>

      {/* Era filter tabs */}
      <div className="flex gap-2 mb-8 flex-wrap">
        {ERA_TABS.map(({ value, label }) => (
          <Link
            key={value}
            href={value ? `/poets?era=${value}` : "/poets"}
            className={`text-xs px-3 py-1.5 rounded-full transition-all border font-arabic ${
              (era || "") === value
                ? "bg-accent/15 text-accent border-accent/40 font-semibold"
                : "text-muted border-border hover:border-border-strong hover:text-secondary"
            }`}
          >
            {label}
          </Link>
        ))}
      </div>

      {/* Poets grid */}
      {poets.length > 0 ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {poets.map((poet: any) => (
            <PoetCard key={poet.id} poet={poet} />
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <p className="font-arabic text-secondary text-lg">لا يوجد شعراء</p>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-10">
          {page > 1 && (
            <Link
              href={`/poets?${era ? `era=${era}&` : ""}page=${page - 1}`}
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
              href={`/poets?${era ? `era=${era}&` : ""}page=${page + 1}`}
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
