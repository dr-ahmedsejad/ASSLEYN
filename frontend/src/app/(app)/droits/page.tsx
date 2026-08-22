import { redirect } from "next/navigation";

import { CreationCompte } from "@/components/CreationCompte";
import { DroitsIndividuels, MatriceParRole } from "@/components/GestionDroits";
import { Alerte, Carte } from "@/components/ui";
import { apiRequest, getCurrentUser } from "@/lib/api";
import { PERMISSIONS } from "@/lib/nav-config";
import type {
  DetailDroitsUtilisateur,
  MatriceDroits,
  UtilisateurDroits,
} from "@/lib/types";

export const metadata = { title: "الصلاحيات — معهد الأصلين" };

/**
 * Attribution des droits.
 *
 * Deux niveaux : ce que donne un role, et ce qu'on confie a une personne en
 * particulier. Le meme code de permission garde l'entree de menu et
 * l'endpoint — il n'y a pas de droit d'affichage sans droit d'acces.
 */
export default async function PageDroits({
  searchParams,
}: {
  searchParams: Promise<{ utilisateur?: string; q?: string }>;
}) {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) redirect("/connexion");

  // Garde cote serveur : le menu masque l'entree, la page la refuse aussi.
  if (!utilisateur.permissions.includes(PERMISSIONS.COMPTES_GERER)) {
    return (
      <div className="space-y-5">
        <h1 className="text-xl font-bold text-dark">الصلاحيات</h1>
        <Carte>
          <Alerte ton="danger">لا تملك الصلاحية اللازمة لهذه الصفحة.</Alerte>
        </Carte>
      </div>
    );
  }

  const parametres = await searchParams;
  const recherche = (parametres.q ?? "").trim();

  const [matrice, utilisateurs] = await Promise.all([
    apiRequest<MatriceDroits>("/rbac/matrice/"),
    apiRequest<UtilisateurDroits[]>(
      `/rbac/utilisateurs/${recherche ? `?search=${encodeURIComponent(recherche)}` : ""}`,
    ),
  ]);

  const choisi = parametres.utilisateur ?? String(utilisateurs[0]?.id ?? "");
  const detail = choisi
    ? await apiRequest<DetailDroitsUtilisateur>(
        `/rbac/utilisateurs/${encodeURIComponent(choisi)}/`,
      ).catch(() => null)
    : null;

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">الأدوار والصلاحيات</h1>

      <CreationCompte />

      <Carte titre="البحث عن مستخدم">
        <form method="get" className="flex flex-wrap items-center gap-2">
          <input
            type="search"
            name="q"
            defaultValue={recherche}
            placeholder="الاسم أو اسم المستخدم"
            aria-label="بحث"
            className="champ max-w-xs"
          />
          <button
            type="submit"
            className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
          >
            بحث
          </button>
        </form>
      </Carte>

      <MatriceParRole matrice={matrice} />

      <DroitsIndividuels utilisateurs={utilisateurs} detail={detail} />
    </div>
  );
}
