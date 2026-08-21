/**
 * Gardes d'acces cote serveur.
 *
 * Le sidebar masque ce a quoi l'utilisateur n'a pas droit, mais une URL se
 * tape a la main. Ces helpers font en sorte qu'une page interdite reponde par
 * un refus lisible plutot que par une erreur de chargement — l'API refuserait
 * de toute facon, mais avec une page cassee.
 */

import "server-only";

import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/api";
import { PERMISSIONS } from "@/lib/nav-config";
import type { CurrentUser } from "@/lib/types";

/**
 * Page d'atterrissage d'un utilisateur, selon ce qu'il a le droit de voir.
 *
 * Sert quand quelqu'un arrive sur une page qui ne le concerne pas — au
 * premier chef la racine, qui n'a de sens que pour qui dispose d'un tableau
 * de bord ou d'un releve.
 */
export function pageDAtterrissage(utilisateur: CurrentUser): string {
  const droits = new Set(utilisateur.permissions);
  if (utilisateur.role === "STUDENT") return "/";
  if (droits.has(PERMISSIONS.TABLEAU_CONSULTER)) return "/";
  if (droits.has(PERMISSIONS.NOTES_SAISIR)) return "/saisie-notes";
  if (droits.has(PERMISSIONS.NOTES_CONSULTER)) return "/resultats";
  if (droits.has(PERMISSIONS.COMPTES_GERER)) return "/droits";
  return "/mot-de-passe";
}

/**
 * Exige une permission pour afficher une page.
 *
 * Retourne l'utilisateur si le droit est la, `null` sinon — a charge de
 * l'appelant d'afficher le refus.
 */
export async function utilisateurAvec(
  permission: string,
): Promise<CurrentUser | null> {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) redirect("/connexion");
  return utilisateur.permissions.includes(permission) ? utilisateur : null;
}
