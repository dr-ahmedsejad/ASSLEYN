/**
 * Regle de mot de passe, cote interface.
 *
 * Huit caracteres au minimum, chiffres compris — regle de l'etablissement. Le
 * mot de passe de premiere connexion d'une etudiante est son matricule ecrit
 * deux fois.
 *
 * Ce qui protege un mot de passe si court n'est pas sa longueur mais le
 * verrouillage progressif : cinq essais, puis la porte se ferme pour 5, 15
 * puis 30 minutes.
 *
 * Le serveur seul fait foi (`apps/accounts/validators.py`). Ce module evite un
 * aller-retour pour une faute evidente, et **porte les memes messages en
 * arabe** : la validation native du navigateur, elle, s'affiche dans la langue
 * de son interface — une etudiante verrait un avertissement en anglais ou en
 * francais au milieu d'un ecran arabe.
 *
 * Module neutre a dessein : ni « use server », ni « server-only ». Il est lu
 * par l'action serveur comme par le formulaire client.
 */

export const LONGUEUR_MINIMALE_MOT_DE_PASSE = 8;

/** Message affiche quand le mot de passe est trop court. */
export const MESSAGE_TROP_COURT = `كلمة السر قصيرة: يجب أن تتكون من ${LONGUEUR_MINIMALE_MOT_DE_PASSE} رموز على الأقل.`;

/** Rappel de la regle, affiche sous le champ. */
export const AIDE_MOT_DE_PASSE = `${LONGUEUR_MINIMALE_MOT_DE_PASSE} رموز على الأقل. الأرقام وحدها مقبولة.`;

/** `null` si le mot de passe convient, sinon le message a afficher. */
export function verifierMotDePasse(valeur: string): string | null {
  if (valeur.length < LONGUEUR_MINIMALE_MOT_DE_PASSE) return MESSAGE_TROP_COURT;
  return null;
}
