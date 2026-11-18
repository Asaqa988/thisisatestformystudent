import type { Metadata } from "next";
import { IBM_Plex_Sans_Arabic } from "next/font/google";

const arabic = IBM_Plex_Sans_Arabic({
  variable: "--font-arabic",
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "المتجر",
  description: "منتجاتنا، مع مساعد صوتي يجيب عن أسئلتك.",
  robots: { index: true, follow: true },
};

/** The public shop page: Arabic, right-to-left, no login and no NEXUS sidebar. */
export default function ShopLayout({ children }: LayoutProps<"/shop">) {
  return (
    <div
      lang="ar"
      dir="rtl"
      className={`${arabic.variable} min-h-full bg-background text-foreground`}
      style={{ fontFamily: "var(--font-arabic), system-ui, sans-serif" }}
    >
      {children}
    </div>
  );
}
