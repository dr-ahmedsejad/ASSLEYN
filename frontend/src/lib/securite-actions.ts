"use server";

import "server-only";

import { revalidatePath } from "next/cache";

import { ApiError, apiRequest } from "@/lib/api";

export interface ResultatDeblocage {
  erreur?: string;
  message?: string;
}

/** Rouvre un compte bloque avant l'expiration de son delai. */
export async function deverrouiller(
  _etat: ResultatDeblocage,
  donnees: FormData,
): Promise<ResultatDeblocage> {
  const id = String(donnees.get("verrou") ?? "");
  if (!id) return { erreur: "لم يتم تحديد الحساب." };

  try {
    await apiRequest(`/securite/verrous/${id}/deverrouiller/`, {
      method: "POST",
    });
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر فتح الحساب." };
    }
    throw erreur;
  }

  revalidatePath("/securite");
  return { message: "تم فتح الحساب." };
}

export interface ResultatReinitialisation {
  erreur?: string;
  username?: string;
  nom?: string;
  motDePasse?: string;
}

/**
 * Reinitialise le mot de passe d'un compte.
 *
 * Le mot de passe est renvoye **une seule fois**, dans cette reponse : il
 * n'est stocke nulle part en clair, et l'ecran qui l'affiche est le seul
 * endroit ou il apparaitra jamais.
 */
export async function reinitialiserMotDePasse(
  _etat: ResultatReinitialisation,
  donnees: FormData,
): Promise<ResultatReinitialisation> {
  const id = String(donnees.get("utilisateur") ?? "");
  const choisi = String(donnees.get("new_password") ?? "").trim();
  if (!id) return { erreur: "لم يتم تحديد الحساب." };

  try {
    const reponse = await apiRequest<{
      username: string;
      full_name_ar: string;
      mot_de_passe: string;
    }>(`/securite/utilisateurs/${id}/reinitialiser-mot-de-passe/`, {
      method: "POST",
      body: choisi ? { new_password: choisi } : {},
    });

    revalidatePath("/droits");
    return {
      username: reponse.username,
      nom: reponse.full_name_ar,
      motDePasse: reponse.mot_de_passe,
    };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر تغيير كلمة السر." };
    }
    throw erreur;
  }
}
