import type { SemesterResult } from "@/lib/types";

/**
 * Un فصل a-t-il ete evalue pour cette etudiante ?
 *
 * La question n'est pas theorique. Un فصل publie dont les notes ne sont pas
 * encore saisies produit un resultat parfaitement forme : moyenne 0,00, rang,
 * decision استدراك. Rien, dans ces chiffres, ne dit qu'ils reposent sur du
 * vide — et une carte partagee annoncerait alors un echec qui n'a pas eu lieu.
 *
 * Le signal fiable est la note elle-meme : `value` reste `null` tant qu'aucune
 * note n'a ete enregistree pour la matiere. Une absence, elle, est saisie et
 * porte une valeur. Il suffit donc qu'une seule matiere ait ete renseignee
 * pour que le فصل compte comme evalue.
 */
export function estEvalue(resultat: SemesterResult): boolean {
  return resultat.subject_results.some((matiere) => matiere.value !== null);
}

/**
 * Le فصل a mettre en avant : le dernier evalue.
 *
 * A defaut — aucune note nulle part — on rend le dernier publie, pour que
 * l'appelant ait toujours de quoi afficher un message explicite plutot
 * qu'une page vide.
 */
export function faslAPresenter(
  semestres: SemesterResult[],
): SemesterResult | null {
  if (semestres.length === 0) return null;
  const evalues = semestres.filter(estEvalue);
  const retenus = evalues.length > 0 ? evalues : semestres;
  return retenus[retenus.length - 1];
}
