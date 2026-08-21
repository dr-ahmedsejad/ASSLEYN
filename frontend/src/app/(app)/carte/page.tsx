import Link from "next/link";

import { CarteResultat } from "@/components/CarteResultat";
import { Refus } from "@/components/Refus";
import { Carte, OngletLien, Onglets, Vide } from "@/components/ui";
import { apiRequest, getCurrentUser } from "@/lib/api";
import { PERMISSIONS } from "@/lib/nav-config";
import type { AnnualResult, SemesterResult } from "@/lib/types";

export const metadata = { title: "بطاقة النتيجة — معهد الأصلين" };

/**
 * Carte de resultat a partager.
 *
 * Une page volontairement pauvre : la carte, et rien autour. Ce qui doit
 * finir dans une capture d'ecran ne doit pas cotoyer des boutons.
 */
export default async function PageCarte({
  searchParams,
}: {
  searchParams: Promise<{ fasl?: string }>;
}) {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) return null;

  if (!utilisateur.permissions.includes(PERMISSIONS.RESULTATS_PERSONNELS)) {
    return <Refus titre="بطاقة النتيجة" />;
  }

  const releve = await apiRequest<{
    semesters: SemesterResult[];
    annual: AnnualResult[];
  }>("/results/me/");

  if (releve.semesters.length === 0) {
    return (
      <div className="space-y-5">
        <h1 className="text-xl font-bold text-dark">بطاقة النتيجة</h1>
        <Carte>
          <Vide>لم تنشر أي نتائج بعد.</Vide>
        </Carte>
      </div>
    );
  }

  const parametres = await searchParams;
  // Par defaut le dernier فصل publie : c'est celui qu'on partage.
  const resultat =
    releve.semesters.find((s) => String(s.semester) === parametres.fasl) ??
    releve.semesters[releve.semesters.length - 1];

  // Le resultat annuel ne rejoint la carte que s'il est complet : afficher une
  // moyenne annuelle calculee sur un seul فصل induirait en erreur.
  const annuel =
    releve.annual.find((a) => a.semester_count >= 2) ?? null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-dark">بطاقة النتيجة</h1>
        <Link
          href="/"
          className="text-sm font-medium text-primary hover:underline"
        >
          النتائج التفصيلية
        </Link>
      </div>

      {releve.semesters.length > 1 ? (
        <Carte>
          <Onglets
            libelle="الفصل"
            enfants={releve.semesters.map((s) => (
              <OngletLien
                key={s.id}
                href={`/carte?fasl=${s.semester}`}
                actif={s.id === resultat.id}
              >
                الفصل {s.semester_number}
              </OngletLien>
            ))}
          />
        </Carte>
      ) : null}

      <CarteResultat
        resultat={resultat}
        annuel={annuel}
        nom={utilisateur.full_name_ar}
      />

      <p className="text-center text-xs text-gris">
        التقط صورة للبطاقة لمشاركتها.
      </p>
    </div>
  );
}
