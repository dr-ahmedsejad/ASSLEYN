/**
 * Client d'API cote serveur (BFF).
 *
 * Le navigateur ne parle jamais directement a Django et ne detient jamais de
 * jeton. Il possede un cookie de session `httpOnly` pose par Next.js ; ce
 * module le relit cote serveur et le rejoue vers l'API.
 *
 * Consequence : un script injecte dans la page n'a aucun moyen de lire la
 * session ni d'appeler l'API en se faisant passer pour l'utilisateur au-dela
 * de ce que le navigateur ferait deja.
 */

import "server-only";

import { cookies, headers } from "next/headers";

import {
  API_BASE_URL,
  API_PREFIX,
  CSRF_COOKIE,
  SESSION_COOKIE,
} from "@/lib/config";
import type { CurrentUser } from "@/lib/types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly payload: unknown,
  ) {
    super(`API ${status}`);
    this.name = "ApiError";
  }

  /** Messages d'erreur en arabe, prets a afficher. */
  get messages(): string[] {
    const payload = this.payload;
    if (typeof payload === "string") return [payload];
    if (!payload || typeof payload !== "object") return [];

    const out: string[] = [];
    for (const value of Object.values(payload as Record<string, unknown>)) {
      if (Array.isArray(value)) out.push(...value.map(String));
      else if (typeof value === "string") out.push(value);
    }
    return out;
  }
}

function buildUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${API_PREFIX}${clean}`;
}

/**
 * Adresse de la personne qui consulte, telle que Nginx l'a observee.
 *
 * Indispensable a cause du BFF : c'est le serveur Next qui appelle Django, si
 * bien que Django voit l'adresse du conteneur Next et non celle du visiteur.
 * Sans ce relais, le journal des connexions inscrivait la meme adresse pour
 * tout le monde, et le plafond de debit s'appliquait a l'institut entier
 * plutot qu'a chaque poste.
 *
 * `x-real-ip` est prefere : Nginx le pose lui-meme, il ne contient qu'une
 * valeur, et le client ne peut pas l'inventer — les trois variantes de
 * configuration ecrasent ces deux en-tetes au lieu d'y ajouter.
 */
export async function adresseClient(): Promise<string | null> {
  const entrantes = await headers();
  const reelle = entrantes.get("x-real-ip");
  if (reelle) return reelle.trim();

  const chaine = entrantes.get("x-forwarded-for");
  return chaine ? (chaine.split(",")[0]?.trim() ?? null) : null;
}

/** En-tetes d'authentification construits a partir des cookies de la requete. */
export async function authHeaders(method: string): Promise<Headers> {
  const jar = await cookies();
  const session = jar.get(SESSION_COOKIE)?.value;
  const csrf = jar.get(CSRF_COOKIE)?.value;

  const headers = new Headers();
  const parts: string[] = [];
  if (session) parts.push(`${SESSION_COOKIE}=${session}`);
  if (csrf) parts.push(`${CSRF_COOKIE}=${csrf}`);
  if (parts.length > 0) headers.set("cookie", parts.join("; "));

  const unsafe = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(
    method.toUpperCase(),
  );
  if (unsafe && csrf) {
    headers.set("X-CSRFToken", csrf);
    // Django verifie l'origine des requetes en ecriture.
    headers.set("Origin", API_BASE_URL);
    headers.set("Referer", API_BASE_URL);
  }

  // Sans cela, Django journalise l'adresse du conteneur Next pour tout le
  // monde. Une seule valeur est transmise, celle que Nginx a observee.
  const adresse = await adresseClient();
  if (adresse) headers.set("X-Forwarded-For", adresse);

  return headers;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Par defaut aucune mise en cache : les notes changent en permanence. */
  cache?: RequestCache;
  signal?: AbortSignal;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers = await authHeaders(method);
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  const response = await fetch(buildUrl(path), {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: options.cache ?? "no-store",
    signal: options.signal,
  });

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const payload = text ? safeJson(text) : null;

  if (!response.ok) throw new ApiError(response.status, payload);
  return payload as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * Utilisateur connecte, ou `null`.
 *
 * Ne leve jamais : les mises en page s'en servent pour decider d'une
 * redirection, pas pour signaler une panne.
 */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await apiRequest<CurrentUser>("/auth/me/");
  } catch {
    return null;
  }
}
