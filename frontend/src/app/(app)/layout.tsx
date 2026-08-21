import { redirect } from "next/navigation";

import Shell from "@/components/layout/Shell";
import { apiRequest, getCurrentUser } from "@/lib/api";
import { resoudreFasl } from "@/lib/contexte";
import type { Paginated, Semester } from "@/lib/types";

/**
 * Coquille des pages authentifiees.
 *
 * Deux redirections defensives : pas de session → page de connexion ; mot de
 * passe temporaire non change → page de changement. Le serveur decide, pas le
 * navigateur.
 *
 * Le layout resout aussi le contexte de travail — le فصل choisi — et le
 * transmet a la barre du haut.
 */
export default async function LayoutApplication({
  children,
}: {
  children: React.ReactNode;
}) {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) redirect("/connexion");
  if (utilisateur.must_change_password) redirect("/mot-de-passe");

  let fusul: Semester[] = [];
  try {
    const reponse = await apiRequest<Paginated<Semester>>("/semesters/");
    fusul = reponse.results;
  } catch {
    // Le selecteur de contexte est un confort : son absence ne doit pas
    // empecher l'affichage des pages.
  }

  const faslCourant = (await resoudreFasl(fusul)) ?? null;

  return (
    <Shell user={utilisateur} fusul={fusul} faslCourant={faslCourant}>
      {children}
    </Shell>
  );
}
