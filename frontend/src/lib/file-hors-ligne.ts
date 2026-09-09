"use client";

/**
 * File d'attente des gestes du jury.
 *
 * La salle où se tient le concours n'a pas de connexion fiable. Un jury qui
 * appuie sur « صحيح » ne doit pas attendre le réseau pour savoir si son geste
 * est passé, et ne doit surtout pas le perdre.
 *
 * Le principe tient en trois points :
 *
 * 1. **Le geste est enregistré localement avant d'être envoyé.** Il survit à
 *    un rechargement de page, à une batterie vide, à un navigateur fermé.
 * 2. **Chaque geste porte un identifiant tiré ici**, et l'heure du navigateur.
 *    Le serveur ignore un identifiant déjà vu : rejouer la file est sans
 *    danger, et l'heure du geste reste celle du geste, pas celle de son
 *    arrivée. Un point accordé à 12 s ne devient pas hors délai parce que le
 *    réseau est revenu deux minutes plus tard.
 * 3. **L'interface avance sans attendre.** L'envoi est une conséquence, pas
 *    une condition.
 *
 * `localStorage` est délibéré : synchrone, donc rien ne se perd entre le clic
 * et l'écriture. Une file de concours compte quelques dizaines d'entrées —
 * IndexedDB serait une machinerie sans objet ici.
 */

const CLE = "asleyn.concours.file";

/**
 * Gestes refusés par le serveur.
 *
 * Un geste écarté doit laisser une trace visible. Sans elle, un jury peut
 * animer une séance entière — lancer, trancher, clore — pendant que le serveur
 * refuse tout et que l'écran de la salle reste immobile. C'est arrivé.
 */
const CLE_REFUS = "asleyn.concours.refus";

export interface GesteEnAttente {
  /** Tiré par le navigateur : c'est lui qui rend le rejeu inoffensif. */
  client_uuid: string;
  chemin: string;
  corps: Record<string, unknown>;
  cree_a: string;
  /** Nombre d'envois tentés. Sert à espacer les reprises. */
  essais: number;
}

function lire(): GesteEnAttente[] {
  if (typeof window === "undefined") return [];
  try {
    const brut = window.localStorage.getItem(CLE);
    return brut ? (JSON.parse(brut) as GesteEnAttente[]) : [];
  } catch {
    // Stockage indisponible — navigation privée, quota. L'application
    // continue : elle enverra directement, sans filet.
    return [];
  }
}

function ecrire(file: GesteEnAttente[]): void {
  try {
    window.localStorage.setItem(CLE, JSON.stringify(file));
  } catch {
    /* rien à faire de plus que continuer */
  }
}

/**
 * Un UUID v4, y compris hors contexte sécurisé.
 *
 * `crypto.randomUUID()` n'existe qu'en contexte sécurisé — HTTPS, ou
 * `localhost`. Servi par son adresse IP en clair, le navigateur ne l'a pas :
 * un serveur d'établissement sans certificat est exactement ce cas. Le serveur
 * attend un UUID et rien d'autre ; un repli qui n'en produirait pas ferait
 * refuser **tous** les gestes du jury, en développement comme nulle part
 * ailleurs, puisque `localhost` masque le problème.
 *
 * `crypto.getRandomValues`, lui, est disponible partout. Les deux octets
 * imposés par la RFC 4122 sont posés à la main : version 4, variante 10xx.
 */
export function identifiant(): string {
  const source = globalThis.crypto;

  if (typeof source?.randomUUID === "function") {
    return source.randomUUID();
  }

  const octets = new Uint8Array(16);
  if (typeof source?.getRandomValues === "function") {
    source.getRandomValues(octets);
  } else {
    // Dernier recours : la valeur n'a pas besoin d'être cryptographique,
    // seulement d'être unique sur cette tablette.
    for (let i = 0; i < octets.length; i += 1) {
      octets[i] = Math.floor(Math.random() * 256);
    }
  }
  octets[6] = (octets[6] & 0x0f) | 0x40;
  octets[8] = (octets[8] & 0x3f) | 0x80;

  const hex = Array.from(octets, (o) => o.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10, 16).join(""),
  ].join("-");
}

/** Dépose un geste. Il partira maintenant si le réseau répond, plus tard sinon. */
export function empiler(
  chemin: string,
  corps: Record<string, unknown>,
): GesteEnAttente {
  const geste: GesteEnAttente = {
    client_uuid: String(corps.client_uuid ?? identifiant()),
    chemin,
    corps,
    cree_a: new Date().toISOString(),
    essais: 0,
  };
  ecrire([...lire(), geste]);
  return geste;
}

export function enAttente(): number {
  return lire().length;
}

/** Un geste que le serveur a refusé pour de bon. */
export interface Refus {
  chemin: string;
  statut: number;
  quand: string;
}

function lireRefus(): Refus[] {
  if (typeof window === "undefined") return [];
  try {
    const brut = window.localStorage.getItem(CLE_REFUS);
    return brut ? (JSON.parse(brut) as Refus[]) : [];
  } catch {
    return [];
  }
}

function noterRefus(refus: Refus): void {
  try {
    // Les dix derniers suffisent : c'est un signal, pas un journal.
    const liste = [...lireRefus(), refus].slice(-10);
    window.localStorage.setItem(CLE_REFUS, JSON.stringify(liste));
  } catch {
    /* rien à faire de plus que continuer */
  }
}

export function refuses(): Refus[] {
  return lireRefus();
}

export function oublierRefus(): void {
  try {
    window.localStorage.removeItem(CLE_REFUS);
  } catch {
    /* rien à faire de plus que continuer */
  }
}

/**
 * Tente d'envoyer la file, dans l'ordre.
 *
 * S'arrête au premier échec réseau : l'ordre compte — le lancement d'un tour
 * doit précéder sa décision, sans quoi le serveur calculerait un dépassement
 * de temps à partir de rien.
 *
 * Une réponse d'erreur du serveur (4xx) retire le geste : le rejouer
 * indéfiniment bloquerait toute la file derrière lui. Une panne réseau, elle,
 * le laisse en place.
 *
 * Renvoie le nombre de gestes restants.
 */
export async function vider(): Promise<number> {
  let file = lire();

  while (file.length > 0) {
    const geste = file[0];
    try {
      const reponse = await fetch(`/api/bff/${geste.chemin}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(geste.corps),
      });

      if (reponse.status >= 500) {
        // Le serveur est là mais en peine : on retentera.
        geste.essais += 1;
        ecrire(file);
        return file.length;
      }

      // Un 4xx est définitif : le rejouer bloquerait la file derrière lui. Il
      // est donc écarté — mais jamais en silence. Le jury doit savoir que son
      // geste n'a pas été enregistré, sur le coup et non trois heures plus
      // tard en découvrant un classement vide.
      if (reponse.status >= 400) {
        noterRefus({
          chemin: geste.chemin,
          statut: reponse.status,
          quand: new Date().toISOString(),
        });
      }

      file = file.slice(1);
      ecrire(file);
    } catch {
      // Réseau absent. La file reste intacte, dans l'ordre.
      geste.essais += 1;
      ecrire(file);
      return file.length;
    }
  }

  return 0;
}

/** Vide la file sans rien envoyer. Réservé à une remise à zéro explicite. */
export function oublier(): void {
  ecrire([]);
}
