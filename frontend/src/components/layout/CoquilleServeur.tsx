import { redirect } from "next/navigation";

import Shell from "@/components/layout/Shell";
import { apiRequest, getCurrentUser } from "@/lib/api";
import { resoudreFasl } from "@/lib/contexte";
import type { Paginated, Semester } from "@/lib/types";

/**
 * Coquille des pages authentifiees : bandeau lateral, barre du haut, contexte.
 *
 * Elle est partagee par deux mises en page, pour une raison de fond. Le layout
 * de `(app)` renvoie vers `/mot-de-passe` tant que le mot de passe est
 * provisoire ; placer cette page-la dans le meme groupe creerait une boucle de
 * redirection. Elle garde donc sa propre mise en page, qui rend la meme
 * coquille avec `exigerMotDePasseChange` a faux.
 *
 * Sans cela, l'ecran de changement de mot de passe apparaissait nu — ni
 * navigation, ni profil — au moment precis ou une etudiante ouvre sa session
 * pour la premiere fois et cherche a se reperer.
 */
export default async function CoquilleServeur({
  children,
  exigerMotDePasseChange = true,
}: {
  children: React.ReactNode;
  /** Renvoie vers `/mot-de-passe` tant que le mot de passe est provisoire. */
  exigerMotDePasseChange?: boolean;
}) {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) redirect("/connexion");
  if (exigerMotDePasseChange && utilisateur.must_change_password) {
    redirect("/mot-de-passe");
  }

  let fusul: Semester[] = [];
  try {
    const reponse = await apiRequest<Paginated<Semester>>("/semesters/");
    fusul = reponse.results;
  } catch {
    // Le selecteur de contexte est un confort : son absence ne doit pas
    // empecher l'affichage des pages. C'est aussi le cas normal tant que le
    // mot de passe est provisoire — l'API ferme alors les routes metier.
  }

  const faslCourant = (await resoudreFasl(fusul)) ?? null;

  return (
    <Shell user={utilisateur} fusul={fusul} faslCourant={faslCourant}>
      {children}
    </Shell>
  );
}
