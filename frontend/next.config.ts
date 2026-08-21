import type { NextConfig } from "next";

/**
 * Origines autorisees a joindre le serveur de developpement.
 *
 * Next bloque par defaut les requetes de developpement — rechargement a
 * chaud, ressources internes — venant d'une autre origine que `localhost`.
 * Sans cette liste, ouvrir l'application depuis un telephone du meme reseau
 * affiche la page mais laisse le rechargement a chaud muet.
 *
 * Cela ne concerne **que** le mode developpement : en production, ce sont
 * `ALLOWED_HOSTS` et `CSRF_TRUSTED_ORIGINS` cote Django qui font foi.
 */
const originesDevAutorisees = [
  "192.168.100.156", // Wi-Fi du poste, pour les tests sur telephone
  "192.168.100.*", // reste du reseau local
  "10.10.0.2",
];

const nextConfig: NextConfig = {
  allowedDevOrigins: originesDevAutorisees,
};

export default nextConfig;
