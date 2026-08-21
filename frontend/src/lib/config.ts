/**
 * Configuration serveur.
 *
 * `API_BASE_URL` n'est jamais exposee au navigateur : toutes les requetes vers
 * Django partent du serveur Next.js. C'est le principe du BFF.
 */

export const API_BASE_URL =
  process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export const API_PREFIX = "/api/v1";

/** Cookie de session pose par Django (voir SESSION_COOKIE_NAME). */
export const SESSION_COOKIE = "asleyn_sid";

/** Cookie CSRF de Django. */
export const CSRF_COOKIE = "csrftoken";

export const IS_PRODUCTION = process.env.NODE_ENV === "production";
