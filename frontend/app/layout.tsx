import type { Metadata, Viewport } from 'next'
import { IBM_Plex_Sans_Arabic, Noto_Naskh_Arabic } from 'next/font/google'
import { Header } from '@/components/layout/Header'
import { Footer } from '@/components/layout/Footer'
import './globals.css'

const ibmPlexSansArabic = IBM_Plex_Sans_Arabic({
  subsets: ['arabic'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-ibm-plex-sans-arabic',
  display: 'swap',
})

const notoNaskhArabic = Noto_Naskh_Arabic({
  subsets: ['arabic'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-noto-naskh-arabic',
  display: 'swap',
})

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: {
    default: "ديوان — منصة الشعر العربي",
    template: "%s | ديوان",
  },
  description: 'اكتشف جمال الشعر العربي — ابحث في آلاف الأبيات والقصائد مع شرح مدعوم بالذكاء الاصطناعي',
  keywords: ['شعر عربي', 'قصائد', 'أبيات شعر', 'ديوان', 'شعراء', 'أدب عربي'],
  openGraph: {
    type: 'website',
    locale: 'ar_SA',
    siteName: 'ديوان',
  },
  twitter: {
    card: 'summary_large_image',
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f7f5f0' },
    { media: '(prefers-color-scheme: dark)', color: '#2a2520' },
  ],
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`${ibmPlexSansArabic.variable} ${notoNaskhArabic.variable} bg-background`}
      suppressHydrationWarning
      style={{ scrollBehavior: "smooth" }}
    >
      <body className="font-sans antialiased min-h-screen flex flex-col">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  )
}
