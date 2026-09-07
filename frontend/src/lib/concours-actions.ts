"use server";

import "server-only";

import { revalidatePath } from "next/cache";

import { ApiError, apiRequest } from "@/lib/api";
import type { Competition } from "@/lib/types";

export interface ResultatConcours {
  erreur?: string;
  message?: string;
  id?: number;
  code?: string;
}

/** Couleurs proposees aux groupes : la charte de l'institut, puis des teintes qui s'en distinguent de loin. */
const COULEURS = [
  "#006633",
  "#C82020",
  "#1d4ed8",
  "#b8930f",
  "#7c3aed",
  "#0f766e",
  "#be185d",
  "#c2410c",
];

export async function creerCompetition(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const name = String(donnees.get("name") ?? "").trim();
  if (!name) return { erreur: "اسم المسابقة مطلوب." };

  const secondes = Number(donnees.get("turn_seconds") ?? 30);
  const poetique = donnees.get("kind") === "POETIQUE";
  const jolees = Number(donnees.get("rounds") ?? 5);

  try {
    const creee = await apiRequest<Competition>("/competitions/", {
      method: "POST",
      body: {
        name,
        kind: poetique ? "POETIQUE" : "CULTURELLE",
        turn_seconds: Number.isFinite(secondes) ? secondes : 30,
        // Le nombre de جولات ne sert qu'a la ندوة شعرية, ou rien d'autre ne
        // dit ou la seance s'arrete. Le serveur l'ignore pour l'autre type.
        rounds: poetique && Number.isFinite(jolees) ? jolees : 5,
        show_question: !poetique && donnees.get("show_question") === "on",
      },
    });
    revalidatePath("/competitions");
    return { id: creee.id, code: creee.code, message: "تم إنشاء المسابقة." };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر إنشاء المسابقة." };
    }
    throw erreur;
  }
}

export async function ajouterGroupe(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");
  const name = String(donnees.get("name") ?? "").trim();
  const rang = Number(donnees.get("rang") ?? 0);
  if (!name) return { erreur: "اسم المجموعة مطلوب." };

  try {
    await apiRequest(`/competitions/${competition}/groupes/`, {
      method: "POST",
      body: { name, color: COULEURS[rang % COULEURS.length] },
    });
    revalidatePath(`/competitions/${competition}`);
    return { message: "تمت الإضافة." };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذرت إضافة المجموعة." };
    }
    throw erreur;
  }
}

/**
 * Ajout des questions, collees en bloc.
 *
 * Une question par ligne. Les questions se preparent ailleurs — un cahier, un
 * document — et se collent ici : les faire saisir une par une serait le
 * meilleur moyen de decourager l'usage la veille du concours.
 */
export async function ajouterQuestions(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");
  const textes = String(donnees.get("textes") ?? "")
    .split("\n")
    .map((ligne) => ligne.trim())
    .filter(Boolean);

  if (textes.length === 0) return { erreur: "لم يُدخل أي سؤال." };

  try {
    await apiRequest(`/competitions/${competition}/questions/`, {
      method: "POST",
      body: { textes },
    });
    revalidatePath(`/competitions/${competition}`);
    return { message: `أُضيف ${textes.length} سؤالا.` };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذرت إضافة الأسئلة." };
    }
    throw erreur;
  }
}

/**
 * Ouvre la competition.
 *
 * C'est ici que tout le deroule est fige : les tours sont crees d'un coup,
 * cote serveur. Apres cela, groupes et questions ne bougent plus — le jury
 * doit pouvoir travailler sans reseau, ce qui suppose que le programme ne
 * change pas sous ses pieds.
 */
export async function demarrerCompetition(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");

  try {
    const reponse = await apiRequest<{ tours: number; code: string }>(
      `/competitions/${competition}/demarrer/`,
      { method: "POST" },
    );
    revalidatePath(`/competitions/${competition}`);
    revalidatePath("/competitions");
    return {
      code: reponse.code,
      message: `انطلقت المسابقة على ${reponse.tours} دورا.`,
    };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر انطلاق المسابقة." };
    }
    throw erreur;
  }
}
