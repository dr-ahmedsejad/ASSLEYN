"use server";

import "server-only";

import { revalidatePath } from "next/cache";

import { ApiError, apiRequest } from "@/lib/api";
import type { Role } from "@/lib/types";

export interface ResultatCreation {
  erreur?: string;
  username?: string;
  nom?: string;
  role?: string;
  motDePasse?: string;
}

/**
 * Ouverture d'un compte.
 *
 * Deux chemins selon ce qui est rempli. Avec un matricule, tout vient du
 * dossier de l'etudiante — identifiant, nom, mot de passe initial — et rien
 * n'est retape. Sans matricule, l'administration saisit l'identifiant, le
 * **nom complet** et le mot de passe.
 *
 * Le nom n'est jamais deduit de l'identifiant : `sejad` n'apprend a personne
 * comment cette personne ecrit son nom.
 */
export async function creerCompte(
  _etat: ResultatCreation,
  donnees: FormData,
): Promise<ResultatCreation> {
  const matricule = String(donnees.get("matricule") ?? "").trim();

  const corps = matricule
    ? { matricule }
    : {
        username: String(donnees.get("username") ?? "").trim(),
        full_name_ar: String(donnees.get("full_name_ar") ?? "").trim(),
        password: String(donnees.get("password") ?? ""),
        role: String(donnees.get("role") ?? "") as Role,
        phone: String(donnees.get("phone") ?? "").trim(),
      };

  try {
    const reponse = await apiRequest<{
      username: string;
      full_name_ar: string;
      role_display: string;
      mot_de_passe: string;
    }>("/rbac/utilisateurs/", { method: "POST", body: corps });

    revalidatePath("/droits");
    return {
      username: reponse.username,
      nom: reponse.full_name_ar,
      role: reponse.role_display,
      motDePasse: reponse.mot_de_passe,
    };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر إنشاء الحساب." };
    }
    throw erreur;
  }
}

export interface ResultatIdentite {
  erreur?: string;
  message?: string;
}

/** Corrige le nom complet — et le téléphone — d'un compte existant. */
export async function corrigerIdentite(
  _etat: ResultatIdentite,
  donnees: FormData,
): Promise<ResultatIdentite> {
  const id = String(donnees.get("utilisateur") ?? "");
  const nom = String(donnees.get("full_name_ar") ?? "").trim();
  if (!id) return { erreur: "لم يتم تحديد الحساب." };
  if (!nom) return { erreur: "الاسم الكامل مطلوب." };

  try {
    await apiRequest(`/rbac/utilisateurs/${id}/`, {
      method: "PATCH",
      body: { full_name_ar: nom },
    });
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر تعديل الاسم." };
    }
    throw erreur;
  }

  revalidatePath("/droits");
  revalidatePath("/comptes");
  revalidatePath("/", "layout");
  return { message: "تم تعديل الاسم." };
}
