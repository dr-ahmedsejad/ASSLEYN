/**
 * Medaille du podium — or, argent, bronze — portant son propre numero.
 *
 * Dessinee ici plutot qu'empruntee a une bibliotheque d'icones, pour une
 * raison apprise a nos depens : la `Medal` de lucide a un « 1 » grave dans
 * son trace. Posee sur la deuxieme place, elle affichait une medaille
 * d'argent frappee du chiffre 1. Un numero qu'on ne controle pas finit
 * toujours par contredire le rang qu'il accompagne.
 *
 * Le ruban est vert pour les trois : c'est le metal qui dit la place, et le
 * vert est celui de l'institut. Le relief tient a trois aplats — bord, metal,
 * lumiere — sans degrade SVG, ce qui laisse la couleur pilotable depuis un
 * seul objet.
 */

interface Metal {
  bord: string;
  disque: string;
  lumiere: string;
  ombre: string;
  chiffre: string;
  libelle: string;
}

const METAUX: Record<number, Metal> = {
  1: {
    bord: "#a8880c",
    disque: "#f0cb2e",
    lumiere: "#fbe98f",
    ombre: "#c99e05",
    chiffre: "#6b5600",
    libelle: "ميدالية ذهبية",
  },
  2: {
    bord: "#74828e",
    disque: "#c2ccd6",
    lumiere: "#eef2f6",
    ombre: "#98a4b0",
    chiffre: "#38434e",
    libelle: "ميدالية فضية",
  },
  3: {
    bord: "#7c4e18",
    disque: "#cf9351",
    lumiere: "#edc294",
    ombre: "#a9702f",
    chiffre: "#4d2f0f",
    libelle: "ميدالية برونزية",
  },
};

/**
 * Ruban vert de l'institut — le defaut, sur les fonds clairs.
 *
 * Il ne convient pas partout : sur le podium, chaque carte porte la couleur de
 * son groupe, et un groupe vert faisait disparaitre le ruban dans le fond. Un
 * groupe dore aurait fait disparaitre la medaille d'or elle-meme.
 */
const RUBAN = "#0a5c33";
const RUBAN_OMBRE = "#043f22";

/**
 * Ruban ivoire, pour les fonds colores.
 *
 * L'ivoire se detache des couleurs saturees comme des sombres, la ou aucune
 * teinte vive ne le ferait sur toutes. Un lisere clair cerne alors le disque :
 * il separe le metal d'un fond qui pourrait avoir sa nuance.
 */
const RUBAN_CLAIR = "#f2eee2";
const RUBAN_CLAIR_OMBRE = "#cfc7b4";

export function Medaille({
  rang,
  taille = 112,
  className = "",
  fondColore = false,
}: {
  /** 1, 2 ou 3. Au-dela, la medaille ne s'affiche pas. */
  rang: number;
  taille?: number;
  className?: string;
  /**
   * La medaille repose sur un fond colore — une carte de podium teintee a la
   * couleur du groupe. Le ruban passe alors a l'ivoire et le disque recoit un
   * lisere clair, pour que la medaille se lise quelle que soit cette couleur.
   */
  fondColore?: boolean;
}) {
  const metal = METAUX[rang];
  if (!metal) return null;

  const ruban = fondColore ? RUBAN_CLAIR : RUBAN;
  const rubanOmbre = fondColore ? RUBAN_CLAIR_OMBRE : RUBAN_OMBRE;

  return (
    <svg
      viewBox="0 0 96 122"
      width={taille}
      height={(taille * 122) / 96}
      role="img"
      aria-label={`${metal.libelle} — المرتبة ${rang}`}
      className={className}
    >
      {/* Rubans : deux pans qui se croisent, le second en retrait pour
          suggerer la pliure. */}
      <path d="M22 0 h20 l20 52 -20 9 Z" fill={ruban} />
      <path d="M74 0 h-20 l-20 52 20 9 Z" fill={rubanOmbre} />

      {/* Disque : bord, metal, puis la lumiere en haut a gauche et
          l'ombre en bas a droite. */}
      {fondColore ? (
        <circle cx="48" cy="82" r="40" fill={RUBAN_CLAIR} opacity="0.9" />
      ) : null}
      <circle cx="48" cy="82" r="38" fill={metal.bord} />
      <circle cx="48" cy="82" r="33" fill={metal.disque} />
      <path
        d="M48 49 a33 33 0 0 0 -33 33 a33 33 0 0 1 33 -33 Z"
        fill={metal.lumiere}
        opacity="0.9"
      />
      <ellipse
        cx="36"
        cy="70"
        rx="18"
        ry="13"
        fill={metal.lumiere}
        opacity="0.45"
        transform="rotate(-30 36 70)"
      />
      <path
        d="M48 115 a33 33 0 0 0 33 -33 a33 33 0 0 1 -33 33 Z"
        fill={metal.ombre}
        opacity="0.8"
      />
      {/* Filet interieur : le detail qui fait lire « medaille » plutot que
          « pastille ». */}
      <circle
        cx="48"
        cy="82"
        r="26"
        fill="none"
        stroke={metal.bord}
        strokeOpacity="0.35"
        strokeWidth="1.5"
      />

      <text
        x="48"
        y="82"
        textAnchor="middle"
        dominantBaseline="central"
        fill={metal.chiffre}
        fontSize="34"
        fontWeight="900"
        fontFamily="Cairo, system-ui, sans-serif"
      >
        {rang}
      </text>
    </svg>
  );
}

/** Libelle arabe de la place, pour le texte qui accompagne la medaille. */
export const LIBELLE_PLACE: Record<number, string> = {
  1: "المرتبة الأولى",
  2: "المرتبة الثانية",
  3: "المرتبة الثالثة",
};

/** Teintes de la pastille de libelle, accordees au metal. */
export const TEINTE_PLACE: Record<number, { fond: string; texte: string }> = {
  1: { fond: "linear-gradient(135deg,#f5d340,#e5c018)", texte: "#6b5600" },
  2: { fond: "linear-gradient(135deg,#d7dee6,#9aa5b1)", texte: "#38434e" },
  3: { fond: "linear-gradient(135deg,#e3ab72,#c07b3a)", texte: "#4d2f0f" },
};
