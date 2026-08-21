import type { ReactNode } from "react";
import Link from "next/link";

import type {
  OverallDecision,
  SemesterState,
  SubjectDecisionCode,
} from "@/lib/types";

/**
 * Grammaire de composants reprise de SIGA : carte blanche a coins arrondis,
 * ombre douce, en-tete separee, pastilles de statut bordees.
 */

export function Carte({
  titre,
  description,
  actions,
  children,
  sansPadding,
}: {
  titre?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  sansPadding?: boolean;
}) {
  return (
    <section className="rounded-2xl border border-gray-100 bg-white shadow-card">
      {titre ? (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-4 py-4 sm:px-5">
          <div className="min-w-0">
            <h2 className="font-semibold text-dark">{titre}</h2>
            {description ? (
              <p className="mt-0.5 text-sm text-gris">{description}</p>
            ) : null}
          </div>
          {actions}
        </header>
      ) : null}
      <div className={sansPadding ? "" : "p-4 sm:p-5"}>{children}</div>
    </section>
  );
}

export function Vide({ children }: { children: ReactNode }) {
  return <p className="py-10 text-center text-sm text-gris">{children}</p>;
}

export function Alerte({
  ton,
  children,
}: {
  ton: "info" | "succes" | "warning" | "danger";
  children: ReactNode;
}) {
  const styles = {
    info: "border-blue-200 bg-blue-50 text-blue-700",
    succes: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-yellow-200 bg-yellow-50 text-yellow-700",
    danger: "border-red-200 bg-red-50 text-red-700",
  } as const;

  return (
    <p
      role={ton === "danger" ? "alert" : "status"}
      className={`rounded-xl border px-3.5 py-2.5 text-sm ${styles[ton]}`}
    >
      {children}
    </p>
  );
}

/* ------------------------------------------------------------------ */
/* Pastilles de statut                                                 */
/* ------------------------------------------------------------------ */

type Variante = "success" | "danger" | "warning" | "info" | "neutral" | "primary";

const STYLES_VARIANTE: Record<Variante, string> = {
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  danger: "bg-red-50 text-red-700 border-red-200",
  warning: "bg-yellow-50 text-yellow-700 border-yellow-200",
  info: "bg-blue-50 text-blue-700 border-blue-200",
  neutral: "bg-gray-100 text-gray-600 border-gray-200",
  primary: "bg-green-50 text-green-700 border-green-200",
};

const POINT_VARIANTE: Record<Variante, string> = {
  success: "bg-emerald-500",
  danger: "bg-red-500",
  warning: "bg-yellow-500",
  info: "bg-blue-500",
  neutral: "bg-gray-400",
  primary: "bg-green-600",
};

export function Pastille({
  libelle,
  variante = "neutral",
  point,
  taille = "sm",
}: {
  libelle: string;
  variante?: Variante;
  point?: boolean;
  taille?: "sm" | "md";
}) {
  const dimension =
    taille === "sm" ? "text-[11px] px-2 py-0.5" : "text-xs px-2.5 py-1";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${STYLES_VARIANTE[variante]} ${dimension}`}
    >
      {point ? (
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${POINT_VARIANTE[variante]}`}
        />
      ) : null}
      {libelle}
    </span>
  );
}

const DECISION_GLOBALE: Record<
  OverallDecision,
  { texte: string; variante: Variante }
> = {
  PASSED: { texte: "ناجحة", variante: "success" },
  RESIT: { texte: "استدراك", variante: "warning" },
};

export function BadgeDecision({
  decision,
  surcharge,
}: {
  decision: OverallDecision;
  surcharge?: boolean;
}) {
  const config = DECISION_GLOBALE[decision];
  return (
    <span className="inline-flex items-center gap-1">
      <Pastille libelle={config.texte} variante={config.variante} point />
      {surcharge ? (
        <span
          title="قرار اللجنة يختلف عن الحساب"
          aria-label="قرار معدّل"
          className="text-xs text-accent"
        >
          ✎
        </span>
      ) : null}
    </span>
  );
}

const DECISION_MATIERE: Record<
  SubjectDecisionCode,
  { texte: string; classe: string }
> = {
  SATISFIED: { texte: "مستوفي", classe: "text-emerald-600" },
  NOT_SATISFIED: { texte: "غير مستوفي", classe: "text-red-600" },
  NOT_APPLICABLE: { texte: "—", classe: "text-gris" },
};

export function DecisionMatiere({ code }: { code: SubjectDecisionCode }) {
  const style = DECISION_MATIERE[code];
  return (
    <span className={`text-[11px] font-medium ${style.classe}`}>
      {style.texte}
    </span>
  );
}

const ETAT_FASL: Record<SemesterState, { texte: string; variante: Variante }> = {
  DRAFT: { texte: "مسودة", variante: "neutral" },
  OPEN: { texte: "مفتوح للإدخال", variante: "info" },
  CLOSED: { texte: "مغلق", variante: "warning" },
  PUBLISHED: { texte: "منشور", variante: "success" },
};

export function BadgeEtat({ etat }: { etat: SemesterState }) {
  const config = ETAT_FASL[etat];
  return <Pastille libelle={config.texte} variante={config.variante} point />;
}

/* ------------------------------------------------------------------ */

/** Nombre en chiffres occidentaux, isole du sens de lecture. */
export function Nombre({ children }: { children: ReactNode }) {
  return <span className="chiffres">{children}</span>;
}

export function BarreProgression({
  fait,
  total,
}: {
  fait: number;
  total: number;
}) {
  const pourcentage = total === 0 ? 0 : Math.round((fait / total) * 100);
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-28 overflow-hidden rounded-full bg-gray-100"
        role="progressbar"
        aria-valuenow={pourcentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="نسبة الإدخال"
      >
        <div
          className="h-full rounded-full transition-all"
          style={{
            inlineSize: `${pourcentage}%`,
            background:
              pourcentage === 100
                ? "#10b981"
                : "linear-gradient(90deg,#006633,#008844)",
          }}
        />
      </div>
      <span className="chiffres text-xs text-gris">
        {fait}/{total}
      </span>
    </div>
  );
}

/** Tuile de statistique du tableau de bord. */
export function Indicateur({
  libelle,
  valeur,
  detail,
  icone,
}: {
  libelle: string;
  valeur: ReactNode;
  detail?: string;
  icone?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-gray-100 bg-white px-4 py-4 shadow-card sm:px-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-gris">{libelle}</p>
          <p className="chiffres mt-1 text-2xl font-bold text-primary">
            {valeur}
          </p>
          {detail ? (
            <p className="mt-0.5 truncate text-xs text-gris">{detail}</p>
          ) : null}
        </div>
        {icone ? (
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white"
            style={{ background: "linear-gradient(135deg,#004d24,#006633)" }}
          >
            {icone}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/** Groupe de filtres en pastilles cliquables. */
export function Onglets({
  libelle,
  enfants,
}: {
  libelle: string;
  enfants: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-full text-xs font-medium text-gris sm:w-auto sm:min-w-16 sm:text-sm">
        {libelle}
      </span>
      {enfants}
    </div>
  );
}

/** Pastille de filtre cliquable, rendue en lien (navigation, pas etat client). */
export function OngletLien({
  href,
  actif,
  children,
}: {
  href: string;
  actif: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={actif ? "page" : undefined}
      className={`rounded-xl border px-3 py-1.5 text-sm transition-colors ${
        actif
          ? "border-primary bg-green-50 font-semibold text-primary"
          : "border-gray-200 text-gris hover:bg-gray-50 hover:text-dark"
      }`}
    >
      {children}
    </Link>
  );
}
