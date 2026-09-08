/**
 * Les sons du chronometre.
 *
 * Une pulsation a chaque seconde ecoulee, puis une cloche a l'expiration.
 * Tout est synthetise : aucun fichier a telecharger, rien a mettre en cache,
 * rien qui manque quand le reseau de la salle lache au milieu d'une seance.
 *
 * **La synchronisation est le point delicat.** Le compte a rebours affiche se
 * calcule a partir de l'heure de depart du tour, corrigee de l'ecart entre
 * l'horloge du serveur et celle de la tablette. Si les sons partaient d'un
 * `setInterval`, ils deriveraient : un intervalle de navigateur se fait
 * bousculer par le rendu, accumule quelques millisecondes a chaque tour, et
 * finit decale du chiffre affiche. A raison d'une pulsation par seconde,
 * l'oreille entend ce decalage tout de suite.
 *
 * Les instants sont donc calcules une fois — l'instant exact ou chaque
 * seconde tombe, dans le meme referentiel que l'affichage — puis **poses
 * d'avance sur l'horloge audio**, qui ne derive pas. Le son et le chiffre
 * changent ensemble, et restent ensemble jusqu'a la fin du tour.
 */

/** Le jury peut couper le son. Le choix suit l'appareil, pas le compte. */
const CLE_MUET = "asleyn.concours.muet";

/** Nombre de secondes finales ou la pulsation monte d'un cran. */
const SECONDES_CHAUDES = 5;

let contexte: AudioContext | null = null;

/** Sortie du tour en cours. La couper fait taire tout ce qui est programme. */
let sortie: GainNode | null = null;

/**
 * Ouvre le contexte audio.
 *
 * Les navigateurs le laissent suspendu tant que l'utilisateur n'a pas touche
 * la page. C'est sans consequence ici : le premier appui sur « ابدأ الدور »
 * fait office de geste, et ouvre le son pour tout le reste de la seance.
 */
function ouvrir(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Fabrique =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!Fabrique) return null;

  if (!contexte) contexte = new Fabrique();
  if (contexte.state === "suspended") void contexte.resume();
  return contexte;
}

/**
 * Une note : une forme d'onde, une hauteur, une enveloppe.
 *
 * L'attaque et la chute sont explicites — couper un oscillateur net produit
 * un claquement qui s'entend plus que la note elle-meme.
 */
function note(
  ctx: AudioContext,
  destination: AudioNode,
  {
    quand,
    hauteur,
    duree,
    volume,
    forme = "sine",
  }: {
    quand: number;
    hauteur: number;
    duree: number;
    volume: number;
    forme?: OscillatorType;
  },
): void {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = forme;
  osc.frequency.setValueAtTime(hauteur, quand);

  gain.gain.setValueAtTime(0.0001, quand);
  gain.gain.exponentialRampToValueAtTime(volume, quand + 0.008);
  gain.gain.exponentialRampToValueAtTime(0.0001, quand + duree);

  osc.connect(gain).connect(destination);
  osc.start(quand);
  osc.stop(quand + duree + 0.05);
}

/** La pulsation d'une seconde ecoulee : ronde, courte, franche. */
function pulsation(
  ctx: AudioContext,
  destination: AudioNode,
  quand: number,
  chaude: boolean,
): void {
  note(ctx, destination, {
    quand,
    hauteur: chaude ? 1240 : 1050,
    duree: 0.085,
    volume: chaude ? 0.42 : 0.36,
  });
}

/**
 * L'expiration : une cloche.
 *
 * Trois sinusoides sur la meme fondamentale, dont la longueur decroit — ce
 * qui donne le timbre d'une cloche plutot que celui d'une note tenue. Elle ne
 * ressemble a rien de ce qui a sonne pendant le tour : c'est ce qui la rend
 * impossible a confondre avec la pulsation.
 */
function cloche(
  ctx: AudioContext,
  destination: AudioNode,
  quand: number,
): void {
  note(ctx, destination, { quand, hauteur: 784, duree: 1.2, volume: 0.32 });
  note(ctx, destination, { quand, hauteur: 1568, duree: 0.7, volume: 0.1 });
  note(ctx, destination, { quand, hauteur: 2350, duree: 0.35, volume: 0.045 });
}

/**
 * Le son est-il reellement ouvert ?
 *
 * Un contexte cree mais suspendu ne joue rien. C'est le cas ordinaire sur
 * l'ecran de la salle : la page est ouverte puis laissee seule, et les
 * navigateurs refusent le son tant que personne n'a touche la page.
 */
export function sonPret(): boolean {
  return contexte !== null && contexte.state === "running";
}

/**
 * Ouvre le son sur un geste de l'utilisateur.
 *
 * Rend `true` quand le son est effectivement disponible. C'est ce que le
 * bouton d'activation appelle : le geste est la condition, on ne peut pas
 * l'obtenir autrement.
 */
export async function reveiller(): Promise<boolean> {
  const ctx = ouvrir();
  if (!ctx) return false;
  if (ctx.state === "suspended") {
    try {
      await ctx.resume();
    } catch {
      return false;
    }
  }
  return ctx.state === "running";
}

/** Le son est-il coupe sur cet appareil ? */
export function estMuet(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(CLE_MUET) === "1";
  } catch {
    // Navigation privee, stockage refuse : on sonne, c'est le defaut.
    return false;
  }
}

export function definirMuet(muet: boolean): void {
  try {
    window.localStorage.setItem(CLE_MUET, muet ? "1" : "0");
  } catch {
    // Sans stockage, le choix ne survit pas au rechargement. Tant pis : il
    // vaut mieux un reglage oublie qu'une page qui casse.
  }
  if (muet) arreter();
}

/** Fait taire le tour en cours. Ce qui etait programme reste inaudible. */
export function arreter(): void {
  if (!sortie || !contexte) return;
  sortie.gain.cancelScheduledValues(contexte.currentTime);
  sortie.gain.setValueAtTime(0, contexte.currentTime);
  sortie.disconnect();
  sortie = null;
}

/**
 * Programme les sons d'un tour, du depart jusqu'a l'expiration.
 *
 * `debut` est l'heure de depart telle que le serveur la connait, et `ecart`
 * la difference mesuree entre son horloge et celle de cette tablette — les
 * deux memes valeurs qui font le compte a rebours affiche. Les sons tombent
 * donc exactement sur les changements de chiffre.
 *
 * Les secondes deja passees sont ignorees : recharger la page au milieu d'un
 * tour ne fait pas sonner les quinze premieres d'un coup.
 */
export function programmerTour({
  debut,
  secondes,
  ecart,
}: {
  debut: string;
  secondes: number;
  ecart: number;
}): void {
  arreter();
  if (estMuet()) return;

  const ctx = ouvrir();
  if (!ctx) return;

  sortie = ctx.createGain();
  sortie.gain.value = 1;
  sortie.connect(ctx.destination);

  const depart = new Date(debut).getTime();
  const maintenant = Date.now() + ecart;

  for (let seconde = 1; seconde <= secondes; seconde += 1) {
    const attente = depart + seconde * 1000 - maintenant;
    if (attente <= 0) continue;

    const quand = ctx.currentTime + attente / 1000;
    const restant = secondes - seconde;

    if (restant === 0) {
      cloche(ctx, sortie, quand);
    } else {
      pulsation(ctx, sortie, quand, restant <= SECONDES_CHAUDES);
    }
  }
}
