import Link from "next/link";

import { CarteResultat } from "@/components/CarteResultat";
import { Refus } from "@/components/Refus";
import { Alerte, Carte, OngletLien, Onglets, Vide } from "@/components/ui";
import { apiRequest, getCurrentUser } from "@/lib/api";
import { estEvalue, faslAPresenter } from "@/lib/evaluation";
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
  // Par defaut le dernier فصل **evalue**, et non le dernier publie.
  //
  // Un فصل publie avant la saisie des notes produit un resultat parfaitement
  // forme — moyenne 0,00, rang, decision استدراك — que rien ne distingue d'un
  // echec reel. Le mettre en avant ferait annoncer a une etudiante, sur une
  // carte destinee au partage, une contre-performance qui n'a pas eu lieu.
  const resultat =
    releve.semesters.find((s) => String(s.semester) === parametres.fasl) ??
    faslAPresenter(releve.semesters)!;

  const evalue = estEvalue(resultat);

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

      {evalue ? (
        <>
          <CarteResultat
            resultat={resultat}
            annuel={annuel}
            nom={utilisateur.full_name_ar}
          />

          <p className="text-center text-xs text-gris">
            التقط صورة للبطاقة لمشاركتها.
          </p>
        </>
      ) : (
        <Carte>
          <Alerte ton="info">
            لم تُدخل نقاط <strong>الفصل {resultat.semester_number}</strong> بعد،
            فلا بطاقة له حتى الآن. ستظهر هنا فور إدخال النقاط واعتماد المداولة.
          </Alerte>
        </Carte>
      )}
    </div>
  );
}
