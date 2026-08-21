import type { Metadata } from "next";
import { Cairo } from "next/font/google";

import "./globals.css";

/**
 * Police arabe embarquee : servie depuis notre propre domaine, jamais depuis
 * un CDN tiers. Cela evite une dependance externe et une fuite d'adresse IP
 * des utilisatrices vers un service tiers.
 */
const cairo = Cairo({
  variable: "--police-arabe",
  subsets: ["arabic", "latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "معهد الأصلين",
  description: "مصلحة الامتحانات",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="ar"
      dir="rtl"
      className={`${cairo.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
