import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface/30 mt-20">
      <div className="max-w-6xl mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 font-arabic text-sm">
          {/* Brand */}
          <div>
            <span className="text-2xl font-bold text-accent">شعر</span>
            <p className="text-muted mt-3 leading-relaxed">
              محرك بحث وكشف للشعر العربي — نجمع بين قوة البحث الذكي وجمال الأدب العربي.
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="text-primary font-semibold mb-4">استكشف</h3>
            <ul className="space-y-2 text-secondary">
              {[
                { href: "/poets",      label: "الشعراء" },
                { href: "/poems",      label: "القصائد" },
                { href: "/categories", label: "التصنيفات" },
                { href: "/search",     label: "البحث المتقدم" },
              ].map(({ href, label }) => (
                <li key={href}>
                  <Link href={href} className="hover:text-accent transition-colors">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Eras */}
          <div>
            <h3 className="text-primary font-semibold mb-4">العصور الشعرية</h3>
            <ul className="space-y-2 text-secondary">
              {[
                { href: "/poets?era=pre_islamic",  label: "الشعر الجاهلي" },
                { href: "/poets?era=abbasid",      label: "الشعر العباسي" },
                { href: "/poets?era=andalusian",   label: "الشعر الأندلسي" },
                { href: "/poets?era=contemporary", label: "الشعر المعاصر" },
              ].map(({ href, label }) => (
                <li key={href}>
                  <Link href={href} className="hover:text-accent transition-colors">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="border-t border-border mt-10 pt-6 flex flex-col md:flex-row justify-between
                        items-center gap-4 text-muted text-xs font-arabic">
          <span>© {new Date().getFullYear()} شعر — جميع الحقوق محفوظة</span>
          <span>صُنع بالحب للشعر العربي ✦</span>
        </div>
      </div>
    </footer>
  );
}
