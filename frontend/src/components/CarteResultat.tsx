import Image from "next/image";
import { Award, Star, Trophy } from "lucide-react";

import type { AnnualResult, SemesterResult } from "@/lib/types";

/**
 * Carte de resultat, pensee pour la capture d'ecran.
 *
 * Tout ce qui compte tient dans un seul bloc aux bords nets : logo, nom,
 * rang, moyenne, decision. Rien qui deborde, aucun element d'interface a
 * rogner — on photographie la carte, pas la page.
 *
 * Le blanc domine, le vert se limite au bandeau et aux accents. Deux raisons :
 * le logo de l'institut est bleu et or, il se perdait sur un fond vert plein ;
 * et une carte claire supporte mieux la capture, quel que soit le fond de la
 * conversation ou elle sera partagee.
 *
 * Les trois premieres places recoivent une distinction : coupe, medaille
 * d'argent, medaille de bronze. Au-dela, le rang reste affiche mais sobre :
 * une carte partagee ne doit pas transformer chaque place en podium.
 *
 * **La fete est reservee a celles qui ont reussi** : confettis, disque qui
 * surgit, reflet sur la mention. Une carte d'استدراك ne recoit aucun de ces
 * trois mouvements — seul le fondu d'apparition, commun a toutes les pages,
 * subsiste. Feliciter un rattrapage serait deplace.
 *
 * C'est `decision_final` qui tranche, pas `decision_computed` : si le conseil
 * a converti un استدراك en reussite, la carte le fete.
 */

interface Podium {
  Icone: typeof Trophy;
  libelle: string;
  fond: string;
  texte: string;
}

/*
 * Aucune de ces icones ne porte de chiffre.
 *
 * C'est une contrainte, pas un gout : la `Medal` de lucide a un « 1 » grave
 * dans son dessin. Posee sur la deuxieme place, elle affichait une medaille
 * d'argent frappee du chiffre 1 — l'image contredisait le texte juste en
 * dessous. Trois silhouettes distinctes, et le rang ecrit une seule fois, dans
 * la pastille.
 */
const PODIUM: Record<number, Podium> = {
  1: {
    Icone: Trophy,
    libelle: "المرتبة الأولى",
    fond: "linear-gradient(135deg,#E5C018,#F5D340)",
    texte: "#7a6300",
  },
  2: {
    Icone: Award,
    libelle: "المرتبة الثانية",
    fond: "linear-gradient(135deg,#9aa5b1,#d7dee6)",
    texte: "#3f4a56",
  },
  3: {
    Icone: Star,
    libelle: "المرتبة الثالثة",
    fond: "linear-gradient(135deg,#c07b3a,#e3ab72)",
    texte: "#5c3512",
  },
};

export function CarteResultat({
  resultat,
  annuel,
  nom,
}: {
  resultat: SemesterResult;
  annuel?: AnnualResult | null;
  nom: string;
}) {
  const distinction = PODIUM[resultat.rank];
  const reussie = resultat.decision_final === "PASSED";

  return (
    <div className="carte-apparition relative mx-auto w-full max-w-sm overflow-hidden rounded-3xl border border-gray-100 bg-white shadow-card-lg">
      {reussie ? <Confettis /> : null}

      {/* Bandeau : d'ou vient cette carte */}
      <div
        className="px-6 pb-12 pt-6 text-center"
        style={{
          background: "linear-gradient(160deg,#004d24 0%,#006633 100%)",
        }}
      >
        <p className="text-base font-bold tracking-wide text-white">
          معهد الأصلين
        </p>
        <p className="chiffres mt-1 text-[11px] text-white/75">
          {resultat.section_name} · الفصل {resultat.semester_number} ·{" "}
          {resultat.session_display}
        </p>
      </div>

      {/* Le logo est bleu et or : il lui faut un fond clair pour se lire. */}
      <div className="-mt-9 flex justify-center">
        <div className="flex h-[4.5rem] w-[4.5rem] items-center justify-center rounded-full bg-white p-2 shadow-card ring-1 ring-gray-100">
          <Image
            src="/logo-institut-carre.png"
            alt="شعار معهد الأصلين"
            width={56}
            height={56}
            className="h-14 w-14 object-contain"
          />
        </div>
      </div>

      {/* Distinction, ou pastille de rang */}
      <div className="relative mt-5 flex flex-col items-center">
        {distinction ? (
          <>
            <div
              className={`relative flex h-24 w-24 items-center justify-center rounded-full shadow-card ${
                reussie ? "pastille-pop" : ""
              }`}
              style={{ background: distinction.fond }}
            >
              <distinction.Icone size={44} style={{ color: distinction.texte }} />

              {/* Le rang, en chiffre, sur la medaille elle-meme : l'image et
                  le texte ne peuvent plus se contredire. */}
              <span
                className="chiffres absolute -bottom-1 flex h-7 w-7 items-center justify-center rounded-full border-2 border-white text-sm font-extrabold leading-none shadow-card"
                style={{ background: distinction.texte, color: "#ffffff" }}
              >
                {resultat.rank}
              </span>
            </div>
            <p
              className="mt-3 rounded-full px-4 py-1 text-sm font-bold"
              style={{ background: distinction.fond, color: distinction.texte }}
            >
              {distinction.libelle}{" "}
              <span className="chiffres font-extrabold">
                من {resultat.cohort_size}
              </span>
            </p>
          </>
        ) : (
          <div
            className={`flex h-24 w-24 flex-col items-center justify-center rounded-full border-4 ${
              reussie ? "pastille-pop" : ""
            }`}
            style={{ borderColor: "#e6f0ea", background: "#f8fafc" }}
          >
            <span className="chiffres text-3xl font-extrabold text-primary">
              {resultat.rank}
            </span>
            <span className="chiffres text-[10px] text-gris">
              من {resultat.cohort_size}
            </span>
          </div>
        )}
      </div>

      {/* Identite */}
      <p className="relative mt-5 px-6 text-center text-2xl font-bold leading-tight text-dark">
        {nom}
      </p>

      {/* Le rang ne figure pas ici : il est deja sur la medaille, et son
          effectif dans le libelle juste dessous. Le repeter une troisieme
          fois encombrerait une carte qui doit tenir dans une capture. */}
      <div className="mt-5 grid grid-cols-1 gap-3 px-5">
        <Bloc libelle="المعدل" valeur={resultat.average_display} accentue />
      </div>

      {annuel ? (
        <div className="mt-3 grid grid-cols-2 gap-3 px-5">
          <Bloc libelle="المعدل السنوي" valeur={annuel.average_display} />
          <Bloc
            libelle="الرتبة السنوية"
            valeur={`${annuel.rank} / ${annuel.cohort_size}`}
          />
        </div>
      ) : null}

      {/* Decision */}
      <div className="relative px-6 py-6 text-center">
        <span
          className={`inline-block rounded-full px-6 py-2 text-sm font-bold text-white ${
            reussie ? "badge-reussite" : ""
          }`}
          style={{
            background: reussie
              ? "linear-gradient(135deg,#006633,#008844)"
              : "linear-gradient(135deg,#b45309,#d97706)",
          }}
        >
          {resultat.decision_display}
        </span>
      </div>

      {/* Pied : les trois couleurs de l'institut */}
      <div className="flex items-center justify-center gap-1.5 border-t border-gray-100 py-4">
        <span
          className="h-1 w-6 rounded-full"
          style={{ background: "#006633" }}
        />
        <span
          className="h-1 w-6 rounded-full"
          style={{ background: "#E5C018" }}
        />
        <span
          className="h-1 w-6 rounded-full"
          style={{ background: "#C82020" }}
        />
      </div>
    </div>
  );
}

/**
 * Confettis de reussite.
 *
 * Les positions viennent de l'index, pas d'un tirage aleatoire : un rendu
 * serveur et un rendu client doivent produire exactement le meme balisage,
 * sinon React signale une divergence d'hydratation.
 */
function Confettis() {
  const couleurs = ["#006633", "#E5C018", "#C82020", "#008844", "#ffffff"];

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {Array.from({ length: 22 }, (_, i) => {
        // Repartition reguliere, decalee pour eviter l'effet de peigne.
        const gauche = (i * 100) / 22 + (i % 3) * 1.5;
        return (
          <span
            key={i}
            className="confetti"
            style={
              {
                insetInlineStart: `${gauche}%`,
                background: couleurs[i % couleurs.length],
                "--derive": `${((i % 5) - 2) * 18}px`,
                "--tour": `${360 + (i % 4) * 180}deg`,
                "--duree": `${2.2 + (i % 5) * 0.28}s`,
                "--attente": `${(i % 7) * 0.14}s`,
              } as React.CSSProperties
            }
          />
        );
      })}
    </div>
  );
}

function Bloc({
  libelle,
  valeur,
  accentue,
}: {
  libelle: string;
  valeur: string;
  accentue?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3.5 text-center">
      <p className="text-[11px] text-gris">{libelle}</p>
      <p
        className={`chiffres mt-0.5 text-xl font-bold ${
          accentue ? "text-primary" : "text-dark"
        }`}
      >
        {valeur}
      </p>
    </div>
  );
}
