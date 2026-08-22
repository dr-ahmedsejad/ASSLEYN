"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

import { FASL_COOKIE } from "@/lib/contexte";
import { COOKIES_SECURE } from "@/lib/config";

/**
 * Memorise le فصل sur lequel l'utilisateur travaille.
 *
 * Le cookie n'a rien de sensible — c'est une preference d'affichage — mais il
 * reste `httpOnly` : le navigateur n'a aucune raison de le lire, et toutes
 * les pages sont rendues cote serveur.
 *
 * `revalidatePath` avec la portee « layout » purge le rendu de toutes les
 * pages : le nouveau contexte s'applique immediatement, y compris a la barre
 * du haut.
 */
export async function choisirFasl(faslId: string): Promise<void> {
  const jar = await cookies();
  jar.set(FASL_COOKIE, faslId, {
    httpOnly: true,
    // `COOKIES_SECURE`, et non `IS_PRODUCTION` : derriere un serveur en clair,
    // un cookie marque `Secure` n'est tout simplement pas conserve par le
    // navigateur. Le choix de فصل n'etait alors jamais memorise, et
    // l'application retombait indefiniment sur le premier فصل.
    secure: COOKIES_SECURE,
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  revalidatePath("/", "layout");
}
