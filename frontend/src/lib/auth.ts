/**
 * Actions d'authentification.
 *
 * Ces fonctions sont le seul endroit ou les cookies de session sont poses ou
 * effaces. Elles s'executent uniquement sur le serveur Next.js.
 */

"use server";

import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import {
  API_BASE_URL,
  API_PREFIX,
  CSRF_COOKIE,
  COOKIES_SECURE,
  SESSION_COOKIE,
} from "@/lib/config";
import {
  adresseClient,
  ApiError,
  apiRequest,
  authHeaders,
} from "@/lib/api";
import { verifierMotDePasse } from "@/lib/politique-mot-de-passe";

export interface FormState {
  error?: string;
  success?: boolean;
  /** Secondes restantes avant reouverture, quand le compte est bloque. */
  secondesRestantes?: number;
  /** Palier atteint : 1, 2 ou 3. Sert a expliquer la duree. */
  niveau?: number;
  /** Essais encore possibles avant blocage. */
  tentativesRestantes?: number;
}

/** Recopie les cookies renvoyes par Django dans la reponse Next.js. */
async function adopterCookies(response: Response): Promise<void> {
  const jar = await cookies();
  for (const brut of response.headers.getSetCookie()) {
    const [paire] = brut.split(";");
    const separateur = paire.indexOf("=");
    if (separateur === -1) continue;

    const nom = paire.slice(0, separateur).trim();
    const valeur = paire.slice(separateur + 1).trim();
    if (nom !== SESSION_COOKIE && nom !== CSRF_COOKIE) continue;

    jar.set(nom, valeur, {
      // Le cookie CSRF doit rester lisible par le serveur Next uniquement :
      // le navigateur n'en a pas besoin puisqu'il ne parle pas a Django.
      httpOnly: true,
      secure: COOKIES_SECURE,
      sameSite: "strict",
      path: "/",
    });
  }
}

/** Recupere un jeton CSRF frais avant toute ecriture. */
async function jetonCsrf(): Promise<string | null> {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/csrf/`, {
    cache: "no-store",
  });
  if (!response.ok) return null;
  await adopterCookies(response);
  const jar = await cookies();
  return jar.get(CSRF_COOKIE)?.value ?? null;
}

export async function connexion(
  _etat: FormState,
  donnees: FormData,
): Promise<FormState> {
  const username = String(donnees.get("username") ?? "").trim();
  const password = String(donnees.get("password") ?? "");

  if (!username || !password) {
    return { error: "الرجاء إدخال اسم المستخدم وكلمة السر." };
  }

  const csrf = await jetonCsrf();
  if (!csrf) {
    return { error: "تعذر الاتصال بالخادم. حاول مرة أخرى." };
  }

  // L'adresse du visiteur doit accompagner la connexion : c'est la requete
  // meme que le journal est cense tracer.
  const adresse = await adresseClient();

  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/login/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrf,
      cookie: `${CSRF_COOKIE}=${csrf}`,
      Origin: API_BASE_URL,
      Referer: API_BASE_URL,
      ...(adresse ? { "X-Forwarded-For": adresse } : {}),
    },
    body: JSON.stringify({ username, password }),
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: string;
      verrouille?: boolean;
      secondes_restantes?: number;
      niveau?: number;
      tentatives_restantes?: number;
    } | null;

    if (response.status === 429) {
      return { error: "عدد المحاولات كبير. انتظر قليلا ثم أعد المحاولة." };
    }

    // 423 : le compte est ferme pour un temps. Le minuteur remonte jusqu'au
    // formulaire, qui l'affiche en decompte plutot que de laisser l'etudiante
    // reessayer dans le vide.
    if (response.status === 423 && payload?.verrouille) {
      return {
        error: payload.detail ?? "تم إقفال الحساب مؤقتا.",
        secondesRestantes: payload.secondes_restantes ?? 0,
        niveau: payload.niveau,
      };
    }

    const messages = new ApiError(response.status, payload).messages;
    return {
      error: payload?.detail ?? messages[0] ?? "اسم المستخدم أو كلمة السر غير صحيحة.",
      tentativesRestantes: payload?.tentatives_restantes,
    };
  }

  await adopterCookies(response);
  const utilisateur = await response.json();

  redirect(utilisateur.must_change_password ? "/mot-de-passe" : "/");
}

export async function deconnexion(): Promise<void> {
  try {
    await apiRequest("/auth/logout/", { method: "POST" });
  } catch {
    // Meme si l'API ne repond pas, la session locale doit disparaitre.
  }
  const jar = await cookies();
  jar.delete(SESSION_COOKIE);
  jar.delete(CSRF_COOKIE);
  redirect("/connexion");
}

export async function changerMotDePasse(
  _etat: FormState,
  donnees: FormData,
): Promise<FormState> {
  const actuel = String(donnees.get("current_password") ?? "");
  const nouveau = String(donnees.get("new_password") ?? "");
  const confirmation = String(donnees.get("confirm_password") ?? "");

  // Verifie ici plutot que de laisser le navigateur le faire : son message
  // natif s'affiche dans la langue de son interface, pas dans celle de
  // l'application.
  const refus = verifierMotDePasse(nouveau);
  if (refus) return { error: refus };

  if (nouveau !== confirmation) {
    return { error: "كلمتا السر غير متطابقتين." };
  }

  // Requete directe plutot que `apiRequest` : Django recycle la cle de session
  // au changement de mot de passe (`update_session_auth_hash`) et renvoie un
  // nouveau cookie. `apiRequest` ne lit pas les cookies de reponse ; le BFF
  // gardait donc l'ancienne session, et l'etudiante se retrouvait a l'ecran de
  // connexion juste apres avoir choisi son mot de passe — au moment meme de sa
  // premiere ouverture de session.
  const entetes = await authHeaders("POST");
  entetes.set("Content-Type", "application/json");
  entetes.set("Accept", "application/json");

  const response = await fetch(
    `${API_BASE_URL}${API_PREFIX}/auth/change-password/`,
    {
      method: "POST",
      headers: entetes,
      body: JSON.stringify({
        current_password: actuel,
        new_password: nouveau,
      }),
      cache: "no-store",
    },
  );

  if (!response.ok) {
    const corps = await response.json().catch(() => null);
    const messages = new ApiError(response.status, corps).messages;
    return { error: messages[0] ?? "تعذر تغيير كلمة السر." };
  }

  await adopterCookies(response);
  redirect("/");
}
