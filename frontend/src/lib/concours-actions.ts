"use server";

import "server-only";

import { revalidatePath } from "next/cache";

import { ApiError, apiRequest, apiRequestFichier } from "@/lib/api";
import type { Competition } from "@/lib/types";

export interface ResultatConcours {
  erreur?: string;
  message?: string;
  id?: number;
  code?: string;
}

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
  if (!name) return { erreur: "اسم المجموعة مطلوب." };

  try {
    // La couleur vient du serveur : la palette est la meme pour un groupe
    // ajoute ici et pour un groupe cree par l'import d'un classeur.
    await apiRequest(`/competitions/${competition}/groupes/`, {
      method: "POST",
      body: { name },
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
 * Import de la composition des groupes depuis un classeur Excel.
 *
 * Deux colonnes : le groupe, puis la participante. Le groupe se repete d'une
 * ligne a l'autre, comme un tableur se remplit. Les groupes deja presents
 * sont completes, pas recrees.
 */
export async function importerGroupes(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");
  const fichier = donnees.get("fichier");

  if (!(fichier instanceof File) || fichier.size === 0) {
    return { erreur: "اختر ملف Excel أولا." };
  }

  const corps = new FormData();
  corps.append("fichier", fichier);

  try {
    const bilan = await apiRequestFichier<{
      groupes: number;
      membres: number;
    }>(`/competitions/${competition}/groupes/classeur/`, corps);
    revalidatePath(`/competitions/${competition}`);

    return {
      message: `أُضيف ${bilan.groupes} مجموعات و${bilan.membres} طالبة.`,
    };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذرت قراءة الملف." };
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
 * Import des questions depuis un classeur Excel.
 *
 * Deux colonnes : l'enonce, puis la reponse. Preparer vingt questions la
 * veille dans un tableur revient moins cher en attention que de les recopier
 * une par une dans un navigateur — surtout quand l'application tourne sur un
 * serveur distant et que chaque saisie attend le reseau.
 */
export async function importerQuestions(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");
  const fichier = donnees.get("fichier");

  if (!(fichier instanceof File) || fichier.size === 0) {
    return { erreur: "اختر ملف Excel أولا." };
  }

  const corps = new FormData();
  corps.append("fichier", fichier);

  try {
    const creees = await apiRequestFichier<{ id: number }[]>(
      `/competitions/${competition}/questions/classeur/`,
      corps,
    );
    revalidatePath(`/competitions/${competition}`);
    return { message: `أُضيف ${creees.length} سؤالا من الملف.` };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذرت قراءة الملف." };
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
 * Ouvre une manche de departage entre les groupes a egalite.
 *
 * La plus haute egalite d'abord, et elle seule. Le jury relance autant de fois
 * qu'il le souhaite — souvent deux, le temps de former le podium — et
 * s'arrete quand le classement lui convient.
 */
export async function lancerBarrage(
  _etat: ResultatConcours,
  donnees: FormData,
): Promise<ResultatConcours> {
  const competition = String(donnees.get("competition") ?? "");

  try {
    const manche = await apiRequest<{ manche: number; groupes: number }>(
      `/competitions/${competition}/barrage/`,
      { method: "POST" },
    );
    revalidatePath(`/competitions/${competition}/animer`);
    return {
      message: `جولة الحسم ${manche.manche} بين ${manche.groupes} مجموعات.`,
    };
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { erreur: erreur.messages[0] ?? "تعذر فتح جولة الحسم." };
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
