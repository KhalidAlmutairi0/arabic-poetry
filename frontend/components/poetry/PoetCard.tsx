import Link from "next/link";
import { BookOpen } from "lucide-react";
import { cn } from "@/lib/utils/cn";

interface Poet {
  id: string;
  name_ar: string;
  name_en?: string;
  slug: string;
  era?: string;
  image_url?: string;
  poem_count?: number;
  verse_count?: number;
}

const ERA_LABELS: Record<string, string> = {
  pre_islamic:    "الجاهلية",
  islamic_early:  "صدر الإسلام",
  umayyad:        "الأموي",
  abbasid:        "العباسي",
  andalusian:     "الأندلسي",
  modern:         "الحديث",
  contemporary:   "المعاصر",
};

export function PoetCard({ poet, className }: { poet: Poet; className?: string }) {
  const eraLabel = poet.era ? ERA_LABELS[poet.era] || poet.era : null;

  return (
    <Link href={`/poets/${poet.slug}`}>
      <div
        className={cn(
          "card p-4 text-center group cursor-pointer transition-all duration-200",
          "hover:bg-surface-elevated hover:border-accent/30",
          className
        )}
      >
        {/* Avatar */}
        <div
          className="w-16 h-16 mx-auto rounded-full bg-gradient-to-br from-accent/20 to-accent/5
                     border border-accent/20 flex items-center justify-center mb-3
                     group-hover:border-accent/40 transition-colors"
        >
          {poet.image_url ? (
            <img
              src={poet.image_url}
              alt={poet.name_ar}
              className="w-full h-full rounded-full object-cover"
            />
          ) : (
            <span className="font-arabic text-xl text-accent">
              {poet.name_ar.charAt(0)}
            </span>
          )}
        </div>

        {/* Name */}
        <h3 className="font-arabic font-bold text-primary text-sm leading-snug group-hover:text-accent transition-colors">
          {poet.name_ar}
        </h3>

        {/* Era */}
        {eraLabel && (
          <span className="text-xs text-muted font-arabic mt-1 block">{eraLabel}</span>
        )}

        {/* Stats */}
        {(poet.poem_count !== undefined) && (
          <div className="flex items-center justify-center gap-1 mt-2 text-xs text-muted">
            <BookOpen size={11} />
            <span className="font-arabic">{poet.poem_count} قصيدة</span>
          </div>
        )}
      </div>
    </Link>
  );
}
