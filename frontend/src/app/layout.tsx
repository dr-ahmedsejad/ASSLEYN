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

/**
 * Adresse publique du site, telle que les gens la partagent.
 *
 * Elle sert a rendre absolues les adresses d'images des apercus : un robot de
 * messagerie ne resout pas les chemins relatifs. En developpement, la valeur
 * de repli suffit — personne ne partage un lien vers sa propre machine.
 */
const ADRESSE_PUBLIQUE = process.env.SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(ADRESSE_PUBLIQUE),
  title: "معهد الأصلين",
  description: "مصلحة الامتحانات",
  icons: { icon: "/favicon.ico" },

  /**
   * Vignette de partage.
   *
   * Posee ici, a la racine, et non sur la page d'accueil : un robot n'a pas
   * de session, il est renvoye vers `/connexion`, et c'est de cette page
   * qu'il lit les balises. Toutes les pages en heritent.
   *
   * Deux images, dans cet ordre : la grande carte, puis le logo carre. Les
   * clients qui n'arrivent pas a charger la premiere retombent sur le second
   * plutot que d'afficher une adresse nue.
   */
  openGraph: {
    type: "website",
    locale: "ar_DZ",
    siteName: "معهد الأصلين",
    title: "معهد الأصلين — مصلحة الامتحانات",
    description: "منصّة النتائج والمسابقات. الدخول بحساب خاصّ.",
    url: "/",
    images: [
      {
        url: "/og-asleyn.png",
        width: 1200,
        height: 630,
        alt: "معهد الأصلين — مصلحة الامتحانات",
      },
      { url: "/logo-institut-carre.png", width: 512, height: 512 },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "معهد الأصلين — مصلحة الامتحانات",
    description: "منصّة النتائج والمسابقات. الدخول بحساب خاصّ.",
    images: ["/og-asleyn.png"],
  },
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
