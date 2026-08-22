"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Search, X } from "lucide-react";

/**
 * Recherche a la frappe.
 *
 * L'URL reste la source de verite : la frappe la reecrit, et c'est le
 * composant serveur qui refait la requete. Le lien demeure partageable, le
 * bouton « precedent » du navigateur fonctionne, et le rendu ne se dedouble
 * pas entre un etat client et un etat serveur.
 *
 * Les autres filtres arrivent en **proprietes**, pas par `useSearchParams`.
 * Ce dernier obligerait a envelopper le champ dans une frontiere de
 * suspension, pour une information que le composant serveur possede deja et
 * n'a qu'a transmettre. Moins de mecanique, et un composant qui s'hydrate
 * comme n'importe quel autre.
 *
 * `replace` et non `push` : trente entrees d'historique pour un mot tape
 * lettre par lettre rendraient le retour arriere inutilisable.
 *
 * Le delai de 250 ms est ce qui separe une recherche vivante d'une requete
 * par caractere. En dessous, le serveur travaille pour rien ; au-dessus, la
 * frappe parait en retard.
 */
export function RechercheInstantanee({
  chemin,
  valeurInitiale,
  placeholder,
  autres = {},
  libelle = "بحث",
}: {
  /** Chemin de la page, sans parametres. */
  chemin: string;
  valeurInitiale: string;
  placeholder: string;
  /** Filtres a conserver dans l'URL. Les valeurs vides sont ignorees. */
  autres?: Record<string, string>;
  libelle?: string;
}) {
  const router = useRouter();
  const [enCours, demarrer] = useTransition();
  const [saisie, setSaisie] = useState(valeurInitiale);

  // Comparaison par valeur : un objet neuf a chaque rendu relancerait l'effet
  // sans fin, chaque navigation en declenchant une autre.
  const cleAutres = JSON.stringify(autres);

  useEffect(() => {
    const propre = saisie.trim();
    // Ne rien faire quand l'URL dit deja ce que dit le champ — a commencer par
    // le premier rendu, qui correspond exactement a ce que le serveur a rendu.
    if (propre === valeurInitiale) return;

    const minuterie = setTimeout(() => {
      const params = new URLSearchParams();
      for (const [cle, valeur] of Object.entries(
        JSON.parse(cleAutres) as Record<string, string>,
      )) {
        if (valeur) params.set(cle, valeur);
      }
      if (propre) params.set("q", propre);
      // Toute recherche repart de la premiere page : rester en page 4 d'un
      // resultat qui n'en compte qu'une afficherait une liste vide.
      const requete = params.toString();

      demarrer(() => {
        router.replace(requete ? `${chemin}?${requete}` : chemin, {
          scroll: false,
        });
      });
    }, 250);

    return () => clearTimeout(minuterie);
  }, [saisie, valeurInitiale, cleAutres, chemin, router]);

  return (
    <div className="relative max-w-sm">
      {/* Ancree explicitement au debut : une boite absolue sans decalage
          reste a sa position statique, ce qui la ferait deriver des que le
          contenu change. */}
      <span
        className="pointer-events-none absolute top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center text-gris"
        style={{ insetInlineStart: "0.25rem" }}
      >
        {enCours ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Search size={16} />
        )}
      </span>

      <input
        type="search"
        name="q"
        value={saisie}
        onChange={(evenement) => setSaisie(evenement.target.value)}
        placeholder={placeholder}
        aria-label={libelle}
        aria-busy={enCours}
        className="champ champ-recherche"
      />

      {saisie ? (
        <button
          type="button"
          onClick={() => setSaisie("")}
          aria-label="مسح البحث"
          title="مسح البحث"
          className="absolute top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-lg text-gris transition-colors hover:bg-gray-50 hover:text-dark"
          style={{ insetInlineEnd: "0.35rem" }}
        >
          <X size={15} />
        </button>
      ) : null}
    </div>
  );
}
