/**
 * Contexte de travail : le فصل sur lequel l'utilisateur est concentre.
 *
 * Le choix est memorise dans un cookie et sert de valeur par defaut a tous
 * les ecrans. Un parametre d'URL explicite reste prioritaire : les liens
 * partages continuent de pointer sur ce qu'ils designent, et le contexte ne
 * les detourne pas.
 */

import "server-only";

import { cookies } from "next/headers";

import type { Semester } from "@/lib/types";

export const FASL_COOKIE = "asleyn_fasl";

/** Identifiant du فصل choisi, tel que stocke. Non verifie. */
export async function getFaslChoisi(): Promise<string | null> {
  const jar = await cookies();
  return jar.get(FASL_COOKIE)?.value ?? null;
}

/**
 * Resout le فصل a afficher, du plus explicite au plus general :
 * parametre d'URL → cookie de contexte → فصل en cours de saisie →
 * premier de la liste.
 *
 * Le cookie est toujours confronte aux فصول reellement disponibles : une
 * valeur perimee (annee archivee, فصل supprime) ne peut pas bloquer un ecran.
 */
export async function resoudreFasl(
  fusul: Semester[],
  parametreUrl?: string,
): Promise<Semester | undefined> {
  const existe = (identifiant: string | null | undefined) =>
    identifiant ? fusul.find((f) => String(f.id) === identifiant) : undefined;

  return (
    existe(parametreUrl) ??
    existe(await getFaslChoisi()) ??
    fusul.find((f) => f.state === "OPEN") ??
    fusul.find((f) => f.state === "CLOSED") ??
    fusul[0]
  );
}
