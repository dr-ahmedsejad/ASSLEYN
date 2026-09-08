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

  try {
    const creee = await apiRequest<Competition>("/competitions/", {
      method: "POST",
      body: {
        name,
        kind: poetique ? "POETIQUE" : "CULTURELLE",
        turn_seconds: Number.isFinite(secondes) ? secondes : 30,
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
    // Le nombre de tours ne veut rien dire pour une ندوة شعرية : ce qu'on cree
    // est une reserve, pas un programme.
    return {
      code: reponse.code,
      message:
        donnees.get("avec_questions") === "1"
          ? `انطلقت المسابقة على ${reponse.tours} دورا.`
          : "انطلقت الندوة. تستمر حتى تُنهيها اللجنة.",
    };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر انطلاق المسابقة." };
    }
    throw erreur;
  }
}

/**
 * Fin d'une ندوة شعرية.
 *
 * Elle n'a pas de dernier tour ecrit d'avance : c'est ce geste, et lui seul,
 * qui la termine. Les tours prepares d'avance et jamais lances disparaissent
 * alors — le compte rendu ne montre que ce qui a eu lieu.
 */
export async function cloturerCompetition(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");

  try {
    await apiRequest(`/competitions/${competition}/cloturer/`, {
      method: "POST",
    });
    revalidatePath(`/competitions/${competition}/animer`);
    revalidatePath("/competitions");
    return { message: "انتهت الندوة." };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر إنهاء الندوة." };
    }
    throw erreur;
  }
}

/**
 * Suppression d'une session, reservee a l'administration.
 *
 * Elle emporte les groupes, les tours et les decisions du jury — la seule
 * trace de ce qui s'est passe dans la salle. Le serveur verifie le role de son
 * cote : cacher le bouton ne protege rien.
 */
export async function supprimerCompetition(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");

  try {
    await apiRequest(`/competitions/${competition}/`, { method: "DELETE" });
    revalidatePath("/competitions");
    return { message: "حُذفت المسابقة." };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر حذف المسابقة." };
    }
    throw erreur;
  }
}
