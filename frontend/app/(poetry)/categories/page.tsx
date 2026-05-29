import type { Metadata } from "next";
import { getCategories } from "@/lib/api/client";
import { CategoryGrid } from "@/components/poetry/CategoryGrid";

export const revalidate = 86400;

export const metadata: Metadata = {
  title: "التصنيفات",
  description: "تصفح الشعر العربي حسب الموضوع — غزل، حكمة، فخر، رثاء، والمزيد.",
};

export default async function CategoriesPage() {
  let categories: any[] = [];
  try {
    const data = await getCategories();
    categories = Array.isArray(data) ? data : [];
  } catch {
    categories = [];
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-10" dir="rtl">
      <div className="mb-8">
        <div className="accent-line mb-3" />
        <h1 className="font-arabic text-3xl font-bold text-primary">التصنيفات</h1>
        <p className="text-muted text-sm font-arabic mt-2">تصفح القصائد حسب الموضوع والغرض الشعري</p>
      </div>

      {categories.length > 0 ? (
        <CategoryGrid categories={categories} />
      ) : (
        <div className="text-center py-20">
          <p className="font-arabic text-secondary text-lg">لا توجد تصنيفات حالياً</p>
        </div>
      )}
    </div>
  );
}
