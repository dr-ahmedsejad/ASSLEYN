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

export function identifiant(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Repli pour un navigateur ancien : la valeur n'a pas besoin d'être
  // cryptographique, seulement d'être unique sur cette tablette.
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
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

      // 2xx comme 4xx : le geste ne sera pas rejoué. Un 4xx signifie que le
      // serveur l'a refusé pour de bon — le garder bloquerait la file.
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
