import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  page: number;
  count: number;
  pageSize: number;
  /** Construit l'URL d'une page. Permet une pagination sans JavaScript. */
  href: (page: number) => string;
  /** Libelle de l'unite comptee, au singulier. */
  unite?: string;
}

/**
 * Pagination.
 *
 * Rendue en liens plutot qu'en boutons : les listes sont produites par des
 * composants serveur, donc changer de page est une navigation — l'URL reste
 * partageable et le bouton « precedent » du navigateur fonctionne.
 *
 * En RTL le sens de lecture s'inverse : le chevron « page precedente » pointe
 * vers la droite, celui de « page suivante » vers la gauche.
 */
export function Pagination({
  page,
  count,
  pageSize,
  href,
  unite = "نتيجة",
}: Props) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  const de = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const a = Math.min(page * pageSize, count);

  // Fenetre glissante : premiere, derniere, et les voisines de la page active.
  const plage: (number | "…")[] = [];
  for (let p = 1; p <= pages; p += 1) {
    if (p === 1 || p === pages || Math.abs(p - page) <= 1) {
      plage.push(p);
    } else if (plage[plage.length - 1] !== "…") {
      plage.push("…");
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-4">
      <p className="text-xs text-gris">
        {pages > 1 ? (
          <>
            <span className="chiffres">{de}</span>–
            <span className="chiffres">{a}</span> من{" "}
          </>
        ) : null}
        <span className="chiffres font-semibold">{count}</span> {unite}
      </p>

      {pages > 1 ? (
        <div className="flex items-center gap-1">
          <LienFleche
            href={href(page - 1)}
            desactive={page === 1}
            libelle="الصفحة السابقة"
          >
            <ChevronRight size={14} />
          </LienFleche>

          {plage.map((p, index) =>
            p === "…" ? (
              <span
                key={`ellipse-${index}`}
                className="select-none px-1 text-xs text-gris"
              >
                …
              </span>
            ) : (
              <Link
                key={p}
                href={href(p)}
                aria-current={p === page ? "page" : undefined}
                className={`chiffres flex h-7 w-7 items-center justify-center rounded-lg text-xs font-medium leading-none transition-colors ${
                  p === page
                    ? "text-white"
                    : "border border-gray-200 text-gris hover:bg-gray-50"
                }`}
                style={
                  p === page
                    ? { background: "linear-gradient(135deg,#006633,#008844)" }
                    : undefined
                }
              >
                {p}
              </Link>
            ),
          )}

          <LienFleche
            href={href(page + 1)}
            desactive={page === pages}
            libelle="الصفحة التالية"
          >
            <ChevronLeft size={14} />
          </LienFleche>
        </div>
      ) : null}
    </div>
  );
}

function LienFleche({
  href,
  desactive,
  libelle,
  children,
}: {
  href: string;
  desactive: boolean;
  libelle: string;
  children: React.ReactNode;
}) {
  const style =
    "flex h-7 w-7 items-center justify-center rounded-lg border border-gray-200 leading-none transition-colors";

  if (desactive) {
    return (
      <span
        aria-disabled="true"
        aria-label={libelle}
        className={`${style} cursor-not-allowed text-gris opacity-40`}
      >
        {children}
      </span>
    );
  }

  return (
    <Link
      href={href}
      aria-label={libelle}
      className={`${style} text-gris hover:bg-gray-50`}
    >
      {children}
    </Link>
  );
}
