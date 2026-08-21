import {
  BookOpenCheck,
  CalendarRange,
  ClipboardList,
  GraduationCap,
  Home,
  KeyRound,
  Layers,
  Scale,
  ScrollText,
  ShieldCheck,
  Siren,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { Role } from "@/lib/types";

/**
 * Arborescence de navigation.
 *
 * Chaque groupe declare la **permission** qui l'ouvre, jamais un role : c'est
 * la meme capacite qui garde l'entree de menu et l'endpoint correspondant.
 * Retirer un droit a un role, ou a une personne, fait disparaitre l'entree et
 * ferme la route du meme mouvement.
 *
 * Un groupe sans permission est visible de tous les utilisateurs connectes.
 */

/** Codes du catalogue cote serveur (`apps/accounts/rbac.py`). */
export const PERMISSIONS = {
  TABLEAU_CONSULTER: "tableau.consulter",
  NOTES_SAISIR: "notes.saisir",
  NOTES_CONSULTER: "notes.consulter",
  DELIBERATION_GERER: "deliberation.gerer",
  STRUCTURE_GERER: "structure.gerer",
  ETUDIANTES_GERER: "etudiantes.gerer",
  ANNEES_GERER: "annees.gerer",
  JOURNAL_CONSULTER: "journal.consulter",
  COMPTES_GERER: "comptes.gerer",
  RESULTATS_PERSONNELS: "resultats.personnels",
} as const;

export interface NavItem {
  href: string;
  label: string;
}

export interface NavGroup {
  key: string;
  label: string;
  icon: LucideIcon;
  /** Titre de section affiche au-dessus du groupe, s'il ouvre une section. */
  section?: string;
  /** Permission requise. Absente : visible de tous. */
  permission?: string;
  /**
   * Roles auxquels l'entree s'adresse, quand elle tient au statut et non a
   * une capacite. L'administration detenant toutes les permissions, c'est le
   * seul moyen de lui epargner une entree qui ne la concerne pas.
   */
  roles?: Role[];
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    key: "accueil",
    label: "الرئيسية",
    icon: Home,
    section: "عام",
    permission: PERMISSIONS.TABLEAU_CONSULTER,
    items: [{ href: "/", label: "لوحة القيادة" }],
  },
  {
    key: "mon-dossier",
    label: "ملفي",
    icon: GraduationCap,
    section: "الطالبة",
    permission: PERMISSIONS.RESULTATS_PERSONNELS,
    roles: ["STUDENT"],
    items: [
      { href: "/", label: "نتائجي" },
      { href: "/carte", label: "بطاقة النتيجة" },
    ],
  },
  {
    key: "saisie",
    label: "النقاط",
    icon: ClipboardList,
    section: "التقويم",
    permission: PERMISSIONS.NOTES_SAISIR,
    items: [{ href: "/saisie-notes", label: "إدخال النقاط" }],
  },
  {
    key: "resultats",
    label: "النتائج",
    icon: BookOpenCheck,
    permission: PERMISSIONS.NOTES_CONSULTER,
    items: [{ href: "/resultats", label: "ترتيب الأقسام" }],
  },
  {
    key: "deliberation",
    label: "المداولة",
    icon: Scale,
    permission: PERMISSIONS.DELIBERATION_GERER,
    items: [{ href: "/deliberation", label: "قرارات اللجنة" }],
  },
  {
    key: "structure",
    label: "البنية البيداغوجية",
    icon: Layers,
    section: "الإدارة",
    permission: PERMISSIONS.STRUCTURE_GERER,
    items: [{ href: "/structure", label: "الأقسام والمواد والضوارب" }],
  },
  {
    key: "annees",
    label: "السنوات الدراسية",
    icon: CalendarRange,
    permission: PERMISSIONS.ANNEES_GERER,
    items: [{ href: "/annees", label: "السنة والتسجيل" }],
  },
  {
    key: "etudiantes",
    label: "الطالبات",
    icon: Users,
    permission: PERMISSIONS.ETUDIANTES_GERER,
    items: [{ href: "/etudiantes", label: "قائمة الطالبات" }],
  },
  {
    key: "audit",
    label: "السجل",
    icon: ScrollText,
    section: "المتابعة",
    permission: PERMISSIONS.JOURNAL_CONSULTER,
    items: [{ href: "/journal", label: "سجل تغييرات النقاط" }],
  },
  {
    key: "securite",
    label: "الزيارات والدخول",
    icon: Siren,
    permission: PERMISSIONS.JOURNAL_CONSULTER,
    items: [{ href: "/securite", label: "الزيارات وسجل الدخول" }],
  },
  {
    key: "droits",
    label: "الصلاحيات",
    icon: ShieldCheck,
    permission: PERMISSIONS.COMPTES_GERER,
    items: [{ href: "/droits", label: "الأدوار والصلاحيات" }],
  },
  {
    key: "compte",
    label: "حسابي",
    icon: KeyRound,
    section: "الحساب",
    items: [{ href: "/mot-de-passe", label: "تغيير كلمة السر" }],
  },
];

/** Groupes visibles pour un role et un jeu de permissions donnes. */
export function resolveGroups(permissions: string[], role: Role): NavGroup[] {
  const accordees = new Set(permissions);
  return NAV_GROUPS.filter((groupe) => {
    if (groupe.permission && !accordees.has(groupe.permission)) return false;
    if (groupe.roles && !groupe.roles.includes(role)) return false;
    return true;
  });
}

/** Un groupe est actif si l'un de ses liens correspond au chemin courant. */
export function isGroupActive(groupe: NavGroup, chemin: string): boolean {
  return groupe.items.some((item) =>
    item.href === "/" ? chemin === "/" : chemin.startsWith(item.href),
  );
}
