import {
  OuvrirAnneeSuivante,
  Reinscription,
} from "@/components/GestionAnnees";
import {
  BadgeEtat,
  Carte,
  Nombre,
  OngletLien,
  Onglets,
  Pastille,
  Vide,
} from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { Refus } from "@/components/Refus";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type {
  AcademicYear,
  Enrollment,
  Paginated,
  Section,
  Semester,
} from "@/lib/types";

export const metadata = { title: "السنوات الدراسية — معهد الأصلين" };

/**
 * Gestion des annees.
 *
 * Tout le systeme est rattache a l'annee : les فصول, les programmes, les
 * notes, les resultats. Ouvrir l'annee suivante recopie la structure ; y
 * inscrire les etudiantes est un acte separe et explicite.
 */
export default async function PageAnnees({
  searchParams,
}: {
  searchParams: Promise<{ source?: string; section?: string }>;
}) {
  // Le sidebar masque cette entree sans la permission ; l'URL, elle,
  // se tape a la main.
  if (!(await utilisateurAvec(PERMISSIONS.ANNEES_GERER))) {
    return <Refus titre="السنوات الدراسية" />;
  }

  const parametres = await searchParams;

  const [annees, sections, fusul] = await Promise.all([
    apiRequest<Paginated<AcademicYear>>("/years/"),
    apiRequest<Paginated<Section>>("/sections/?is_active=true"),
    apiRequest<Paginated<Semester>>("/semesters/"),
  ]);

  const active = annees.results.find((a) => a.is_active) ?? annees.results[0];
  const sourceChoisie = parametres.source ?? String(active?.id ?? "");
  const sectionChoisie =
    parametres.section ?? String(sections.results[0]?.id ?? "");

  const inscriptions =
    sourceChoisie && sectionChoisie
      ? await apiRequest<Paginated<Enrollment>>(
          `/enrollments/?year=${sourceChoisie}&section=${sectionChoisie}` +
            "&is_active=true&page_size=200&ordering=student__matricule",
        )
      : null;

  const lien = (modifications: Partial<{ source: string; section: string }>) => {
    const params = new URLSearchParams({
      source: modifications.source ?? sourceChoisie,
      section: modifications.section ?? sectionChoisie,
    });
    return `/annees?${params.toString()}`;
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">السنوات الدراسية</h1>

      <Carte
        titre="السنوات"
        description="سنة واحدة فقط تكون جارية. كل النقاط والنتائج مرتبطة بسنتها."
        sansPadding
      >
        {annees.results.length === 0 ? (
          <Vide>لا توجد سنة دراسية.</Vide>
        ) : (
          <ul className="divide-y divide-gray-100">
            {annees.results.map((annee) => {
              const sesFusul = fusul.results.filter((f) => f.year === annee.id);
              return (
                <li key={annee.id} className="px-4 py-3.5 sm:px-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-dark">
                        <Nombre>{annee.label}</Nombre>
                      </p>
                      <p className="chiffres text-sm text-gris">
                        {annee.start_date} → {annee.end_date}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {annee.is_active ? (
                        <Pastille libelle="السنة الجارية" variante="success" point />
                      ) : (
                        <Pastille libelle="سنة سابقة" variante="neutral" />
                      )}
                      {sesFusul.map((f) => (
                        <span
                          key={f.id}
                          className="flex items-center gap-1 text-xs text-gris"
                        >
                          <Nombre>ف{f.number}</Nombre>
                          <BadgeEtat etat={f.state} />
                        </span>
                      ))}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Carte>

      {active ? <OuvrirAnneeSuivante source={active} /> : null}

      <Carte titre="اختر مصدر التسجيل">
        <div className="space-y-3">
          <Onglets
            libelle="السنة"
            enfants={annees.results.map((annee) => (
              <OngletLien
                key={annee.id}
                href={lien({ source: String(annee.id) })}
                actif={String(annee.id) === sourceChoisie}
              >
                {annee.label}
              </OngletLien>
            ))}
          />
          <Onglets
            libelle="القسم"
            enfants={sections.results.map((section) => (
              <OngletLien
                key={section.id}
                href={lien({ section: String(section.id) })}
                actif={String(section.id) === sectionChoisie}
              >
                {section.name_ar}
              </OngletLien>
            ))}
          />
        </div>
      </Carte>

      <Reinscription
        inscriptions={inscriptions?.results ?? []}
        annees={annees.results}
        sections={sections.results}
        anneeCourante={Number(sourceChoisie) || null}
      />
    </div>
  );
}
