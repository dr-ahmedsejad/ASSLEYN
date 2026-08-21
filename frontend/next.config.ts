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

  /**
   * Build autonome pour la mise en conteneur.
   *
   * Next reconstruit alors un `node_modules` reduit aux seuls modules que le
   * serveur atteint reellement, et produit un `server.js` qui se lance sans
   * npm. L'image de production n'embarque plus l'arbre de dependances complet
   * — ni les outils de build, ni ce qui ne sert qu'au developpement.
   */
  output: "standalone",
};

export default nextConfig;
