"use client";

import { Share2 } from "lucide-react";

interface ShareButtonProps {
  text: string;
}

export function ShareButton({ text }: ShareButtonProps) {
  return (
    <button
      onClick={() => {
        if (navigator.share) {
          navigator.share({ text, url: window.location.href });
        } else {
          navigator.clipboard?.writeText(text);
        }
      }}
      className="flex items-center gap-1.5 text-sm text-muted hover:text-accent
                 transition-colors font-arabic"
    >
      <Share2 size={14} />
      مشاركة
    </button>
  );
}
