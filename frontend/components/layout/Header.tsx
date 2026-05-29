"use client";

import Link from "next/link";
import { useState } from "react";
import { Search, Menu, X, Moon, Sun } from "lucide-react";

export function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [isDark, setIsDark] = useState(true);

  const toggleTheme = () => {
    const newTheme = isDark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", newTheme);
    setIsDark(!isDark);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <span className="font-arabic text-2xl font-bold text-accent group-hover:text-accent-light transition-colors">
            شعر
          </span>
          <span className="text-muted text-xs hidden sm:block mt-0.5">
            Arabic Poetry
          </span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6 font-arabic text-sm text-secondary">
          <Link href="/search" className="hover:text-primary transition-colors flex items-center gap-1.5">
            <Search size={14} />
            بحث
          </Link>
          <Link href="/poets" className="hover:text-primary transition-colors">الشعراء</Link>
          <Link href="/poems" className="hover:text-primary transition-colors">القصائد</Link>
          <Link href="/categories" className="hover:text-primary transition-colors">التصنيفات</Link>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={toggleTheme}
            className="p-2 text-muted hover:text-primary rounded-lg hover:bg-surface-elevated transition-colors"
            aria-label="تبديل الثيم"
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {/* Mobile menu */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-2 text-muted hover:text-primary rounded-lg hover:bg-surface-elevated transition-colors"
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden border-t border-border bg-surface py-4 px-4">
          <nav className="flex flex-col gap-3 font-arabic text-sm text-secondary">
            {[
              { href: "/search",     label: "بحث" },
              { href: "/poets",      label: "الشعراء" },
              { href: "/poems",      label: "القصائد" },
              { href: "/categories", label: "التصنيفات" },
            ].map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className="hover:text-primary transition-colors py-2 border-b border-border last:border-0"
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
