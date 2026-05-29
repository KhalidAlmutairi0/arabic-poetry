import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPoem } from "@/lib/api/client";
import { PoemReader } from "@/components/poetry/PoemReader";
import { ChevronLeft } from "lucide-react";

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const poem = await getPoem(slug);
    const firstVerse = poem.verses?.[0]?.full_verse || "";
    return {
      title: `${poem.title_ar} — ${poem.poet?.name_ar}`,
      description: firstVerse.slice(0, 160),
      openGraph: {
        title: `${poem.title_ar} | شعر`,
        description: firstVerse,
        type: "article",
      },
    };
  } catch {
    return { title: "قصيدة | شعر" };
  }
}

export default async function PoemPage({ params }: Props) {
  const { slug } = await params;

  let poem: any;
  try {
    poem = await getPoem(slug);
  } catch {
    notFound();
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-10" dir="rtl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted mb-8 font-arabic">
        <Link href="/" className="hover:text-accent transition-colors">الرئيسية</Link>
        <ChevronLeft size={14} className="rotate-180" />
        <Link href="/poems" className="hover:text-accent transition-colors">القصائد</Link>
        <ChevronLeft size={14} className="rotate-180" />
        <span className="text-secondary">{poem.title_ar}</span>
      </nav>

      <PoemReader poem={poem} verses={poem.verses || []} />
    </div>
  );
}
