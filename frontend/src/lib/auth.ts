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
  IS_PRODUCTION,
  SESSION_COOKIE,
} from "@/lib/config";
import { ApiError, apiRequest } from "@/lib/api";

export interface FormState {
  error?: string;
  success?: boolean;
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
      secure: IS_PRODUCTION,
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

  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/login/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrf,
      cookie: `${CSRF_COOKIE}=${csrf}`,
      Origin: API_BASE_URL,
      Referer: API_BASE_URL,
    },
    body: JSON.stringify({ username, password }),
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const messages = new ApiError(response.status, payload).messages;
    if (response.status === 429) {
      return { error: "عدد المحاولات كبير. انتظر قليلا ثم أعد المحاولة." };
    }
    return {
      error: messages[0] ?? "اسم المستخدم أو كلمة السر غير صحيحة.",
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

  if (nouveau !== confirmation) {
    return { error: "كلمتا السر غير متطابقتين." };
  }

  try {
    await apiRequest("/auth/change-password/", {
      method: "POST",
      body: { current_password: actuel, new_password: nouveau },
    });
  } catch (erreur) {
    if (erreur instanceof ApiError) {
      return { error: erreur.messages[0] ?? "تعذر تغيير كلمة السر." };
    }
    throw erreur;
  }

  redirect("/");
}
