import { notFound } from "next/navigation";

import { EcranSalle } from "@/components/EcranSalle";
import { API_BASE_URL, API_PREFIX } from "@/lib/config";
import type { EcranDirect } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  return { title: `المسابقة ${code.toUpperCase()} — معهد الأصلين` };
}

/**
 * Ecran de la salle — ouvert a tous, sans connexion.
 *
 * Hors du groupe authentifie, comme la page de connexion : c'est un lien qu'on
 * projette ou qu'on partage, et demander un compte a une salle n'aurait aucun
 * sens.
 *
 * Le premier rendu vient du serveur, pour que la projection affiche le score
 * immediatement ; le composant client prend ensuite le relais par sondage.
 */
export default async function PageDirect({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;

  const reponse = await fetch(
    `${API_BASE_URL}${API_PREFIX}/direct/${code.toUpperCase()}/`,
    { cache: "no-store", headers: { Accept: "application/json" } },
  );
  if (!reponse.ok) notFound();

  const initial = (await reponse.json()) as EcranDirect;

  return (
    /* Fond clair : c'est l'ecran que la salle regarde le plus longtemps, et
       le sceau de l'institut — bleu et or — s'y tient mieux que sur le vert
       sombre. La teinte verte reste, en halo, tout en haut. */
    <div
      className="min-h-screen"
      style={{
        background:
          "radial-gradient(1200px 600px at 50% -22%, rgba(0,102,51,.12), transparent 68%), #f2f7f4",
      }}
    >
      <EcranSalle code={code.toUpperCase()} initial={initial} />
    </div>
  );
}
