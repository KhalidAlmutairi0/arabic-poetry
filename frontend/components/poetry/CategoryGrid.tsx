import Link from "next/link";
import { cn } from "@/lib/utils/cn";

interface Category {
  id: string;
  name_ar: string;
  slug: string;
  icon?: string;
  color?: string;
  poem_count?: number;
}

export function CategoryGrid({ categories, className }: { categories: Category[]; className?: string }) {
  return (
    <div className={cn("grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3", className)}>
      {categories.map((cat) => (
        <Link key={cat.id} href={`/categories/${cat.slug}`}>
          <div
            className="card p-4 text-center group cursor-pointer transition-all duration-200
                       hover:bg-surface-elevated hover:scale-[1.02]"
            style={{ borderColor: cat.color ? `${cat.color}30` : undefined }}
          >
            {cat.icon && (
              <span className="text-2xl block mb-2">{cat.icon}</span>
            )}
            <h3
              className="font-arabic text-sm font-semibold text-primary group-hover:text-accent
                         transition-colors"
            >
              {cat.name_ar}
            </h3>
            {cat.poem_count !== undefined && cat.poem_count > 0 && (
              <span className="text-xs text-muted font-arabic mt-1 block">
                {cat.poem_count} قصيدة
              </span>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
