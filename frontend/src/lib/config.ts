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

/**
 * Marque `Secure` sur les cookies poses par le BFF.
 *
 * Vrai en production par defaut. Un cookie `Secure` n'est pas envoye sur une
 * page en clair : le laisser vrai derriere un serveur en HTTP empecherait
 * toute connexion — personne ne resterait authentifie.
 *
 * `COOKIES_SECURE=false` n'a donc qu'un usage : un serveur joint en clair, ou
 * l'on accepte sciemment que les cookies de session circulent lisibles. Le
 * reglage jumeau cote Django est `DJANGO_HTTPS`.
 */
export const COOKIES_SECURE =
  process.env.COOKIES_SECURE === undefined
    ? IS_PRODUCTION
    : process.env.COOKIES_SECURE !== "false";
