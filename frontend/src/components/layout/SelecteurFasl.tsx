"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Check, ChevronDown } from "lucide-react";

import { choisirFasl } from "@/lib/contexte-actions";
import type { Semester } from "@/lib/types";

/**
 * Selecteur de contexte de la barre du haut : sur quel فصل travaille-t-on.
 *
 * Le choix est memorise cote serveur et devient la valeur par defaut de tous
 * les ecrans. Comme un parametre d'URL explicite reste prioritaire, changer
 * de contexte retire le `fasl` de l'URL courante — sans quoi la page
 * continuerait d'afficher l'ancien. Les autres filtres (قسم, دورة) sont
 * conserves.
 */
export default function SelecteurFasl({
  fusul,
  courant,
}: {
  fusul: Semester[];
  courant: Semester | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [ouvert, setOuvert] = useState(false);
  const [enCours, demarrer] = useTransition();
  const conteneur = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ouvert) return;
    function surClic(event: MouseEvent) {
      if (
        conteneur.current &&
        !conteneur.current.contains(event.target as Node)
      ) {
        setOuvert(false);
      }
    }
    function surTouche(event: KeyboardEvent) {
      if (event.key === "Escape") setOuvert(false);
    }
    document.addEventListener("mousedown", surClic);
    document.addEventListener("keydown", surTouche);
    return () => {
      document.removeEventListener("mousedown", surClic);
      document.removeEventListener("keydown", surTouche);
    };
  }, [ouvert]);

  if (fusul.length === 0) return null;

  function appliquer(fasl: Semester) {
    setOuvert(false);
    demarrer(async () => {
      await choisirFasl(String(fasl.id));

      const params = new URLSearchParams(searchParams.toString());
      // On retire ce qui appartient a un فصل precis : le garder ferait
      // revenir l'ancien فصل par la bande, puisqu'un parametre explicite
      // prime sur le contexte.
      for (const cle of ["fasl", "curriculum", "page"]) {
        params.delete(cle);
      }
      const requete = params.toString();
      router.replace(requete ? `${pathname}?${requete}` : pathname);
      router.refresh();
    });
  }

  return (
    <div ref={conteneur} className="relative">
      <button
        type="button"
        onClick={() => setOuvert((v) => !v)}
        disabled={enCours}
        aria-expanded={ouvert}
        aria-haspopup="listbox"
        title="تغيير الفصل الذي تعمل عليه"
        className="flex items-center gap-1.5 rounded-xl border border-gray-100 bg-gray-50 px-2.5 py-1.5 transition-colors hover:bg-gray-100 disabled:opacity-60 sm:px-3"
      >
        <span className="chiffres text-xs font-bold text-dark">
          {courant?.year_label ?? "—"}
        </span>
        <span className="h-3 w-px bg-gray-300" />
        <span className="text-xs font-medium text-primary">
          {courant ? `الفصل ${courant.number}` : "—"}
        </span>
        <ChevronDown
          size={13}
          className={`text-gris transition-transform ${
            ouvert ? "rotate-180" : ""
          }`}
        />
      </button>

      {ouvert ? (
        <div
          role="listbox"
          aria-label="الفصل الدراسي"
          className="absolute end-0 z-50 mt-2 w-64 overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-card-lg"
        >
          <p className="border-b border-gray-100 px-4 py-2.5 text-xs font-semibold text-dark-soft">
            الفصل الذي تعمل عليه
          </p>

          <ul className="max-h-72 overflow-y-auto py-1">
            {fusul.map((fasl) => {
              const actif = fasl.id === courant?.id;
              return (
                <li key={fasl.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={actif}
                    onClick={() => appliquer(fasl)}
                    className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-start transition-colors ${
                      actif
                        ? "bg-green-50 text-primary"
                        : "text-dark-soft hover:bg-gray-50"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className="block text-sm font-medium">
                        الفصل {fasl.number}
                        <span className="chiffres mx-1.5 text-xs font-normal text-gris">
                          {fasl.year_label}
                        </span>
                      </span>
                      <span className="block text-[11px] text-gris">
                        {fasl.state_display} · {fasl.current_session_display}
                      </span>
                    </span>
                    {actif ? (
                      <Check size={15} className="shrink-0 text-primary" />
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>

          <p className="border-t border-gray-100 px-4 py-2.5 text-[11px] leading-relaxed text-gris">
            يُطبَّق هذا الاختيار على كل الشاشات: النقاط، النتائج، المداولة
            والبنية.
          </p>
        </div>
      ) : null}
    </div>
  );
}
