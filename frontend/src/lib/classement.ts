/**
 * Le classement d'un concours, calcule sur le poste du jury.
 *
 * Le serveur sait deja le faire — mais la console doit rester juste **sans
 * reseau**, puisque c'est toute sa raison d'etre. Le calcul existe donc en
 * deux endroits, et cette duplication n'est acceptable qu'a une condition :
 * que les deux donnent exactement le meme resultat. Le jury et la salle
 * regardent le meme concours ; deux classements qui different sur le meme
 * ecart de points sont indefendables devant une assemblee.
 *
 * D'ou ce module a part, verifiable seul, plutot qu'une trentaine de lignes
 * enfouies dans un composant.
 *
 * Les trois regles, identiques a celles du serveur :
 *
 * - **les tours de departage ne rapportent aucun point.** Ils ordonnent des
 *   groupes deja a egalite, sans jamais leur faire depasser quelqu'un qu'ils
 *   n'avaient pas rattrape ;
 * - **ils se comparent manche par manche, jamais en somme.** Une victoire a la
 *   premiere manche se gagne contre tout le monde ; a la seconde, seulement
 *   contre ceux qui avaient deja perdu ;
 * - **le rang se partage** quand rien n'a departage — classement dense, comme
 *   partout ailleurs dans l'application.
 */

/** Ce que le calcul lit d'un tour. Volontairement moins que le type complet. */
export interface TourClassable {
  group: number;
  group_name: string;
  group_color: string;
  outcome: string;
  tiebreak_round: number;
}

export interface LigneLocale {
  name: string;
  color: string;
  points: number;
  /** Resultat manche par manche des departages, dans l'ordre des manches. */
  departage: number[];
  rank: number;
}

export function classerLocalement(tours: TourClassable[]): LigneLocale[] {
  const manches = tours.reduce(
    (haut, tour) => Math.max(haut, tour.tiebreak_round),
    0,
  );

  const parGroupe = new Map<
    number,
    {
      name: string;
      color: string;
      points: number;
      departage: number[];
      ordre: number;
    }
  >();

  tours.forEach((tour, position) => {
    const ligne = parGroupe.get(tour.group) ?? {
      name: tour.group_name,
      color: tour.group_color,
      points: 0,
      departage: Array.from({ length: manches }, () => 0),
      ordre: position,
    };
    if (tour.outcome === "CORRECT") {
      if (tour.tiebreak_round === 0) ligne.points += 1;
      else ligne.departage[tour.tiebreak_round - 1] = 1;
    }
    parGroupe.set(tour.group, ligne);
  });

  const ordonnees = [...parGroupe.values()].sort((a, b) => {
    if (a.points !== b.points) return b.points - a.points;
    for (let manche = 0; manche < manches; manche += 1) {
      if (a.departage[manche] !== b.departage[manche]) {
        return b.departage[manche] - a.departage[manche];
      }
    }
    // A egalite parfaite, l'ordre d'apparition : c'est celui des groupes, et
    // il ne change pas d'un affichage a l'autre.
    return a.ordre - b.ordre;
  });

  let rang = 0;
  let precedent: string | null = null;
  return ordonnees.map(({ ordre: _ordre, ...ligne }) => {
    const marque = `${ligne.points}|${ligne.departage.join("")}`;
    if (marque !== precedent) {
      rang += 1;
      precedent = marque;
    }
    return { ...ligne, rank: rang };
  });
}

/**
 * Les groupes de la plus haute egalite non resolue, ou une liste vide.
 *
 * Une seule egalite a la fois, et la plus haute d'abord — meme regle qu'au
 * serveur. Ce calcul doit vivre ici, et non venir du serveur : la console
 * joue hors ligne, ses scores evoluent sans que rien ne soit envoye, et une
 * liste recue au chargement de la page annoncerait l'egalite du depart —
 * celle ou tout le monde est a zero point.
 */
export function groupesADepartager(lignes: LigneLocale[]): LigneLocale[] {
  const compte = new Map<number, number>();
  lignes.forEach((ligne) => {
    compte.set(ligne.rank, (compte.get(ligne.rank) ?? 0) + 1);
  });

  // `lignes` est deja trie du meilleur rang au dernier.
  const premiere = lignes.find((ligne) => (compte.get(ligne.rank) ?? 0) > 1);
  return premiere ? lignes.filter((l) => l.rank === premiere.rank) : [];
}
