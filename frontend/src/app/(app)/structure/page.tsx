import {
  CatalogueMatieres,
  GestionProgramme,
} from "@/components/GestionProgramme";
import {
  BadgeEtat,
  Carte,
  Nombre,
  OngletLien,
  Onglets,
  Vide,
} from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { Refus } from "@/components/Refus";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import { resoudreFasl } from "@/lib/contexte";
import type {
  Curriculum,
  Paginated,
  Section,
  Semester,
  Subject,
} from "@/lib/types";

export const metadata = { title: "البنية البيداغوجية — معهد الأصلين" };

/**
 * Structure pedagogique : quelles matieres, dans quelle section, pour quel
 * فصل, avec quel coefficient. C'est l'ecran d'edition de la table pivot
 * `Curriculum` — celle qui gouverne tous les calculs.
 */
export default async function PageStructure({
  searchParams,
}: {
  searchParams: Promise<{ section?: string; fasl?: string }>;
}) {
  // Le sidebar masque cette entree sans la permission ; l'URL, elle,
  // se tape a la main.
  if (!(await utilisateurAvec(PERMISSIONS.STRUCTURE_GERER))) {
    return <Refus titre="البنية البيداغوجية" />;
  }

  const parametres = await searchParams;

  const [sections, fusul, matieres, programmes] = await Promise.all([
    apiRequest<Paginated<Section>>("/sections/?is_active=true"),
    apiRequest<Paginated<Semester>>("/semesters/"),
    apiRequest<Paginated<Subject>>("/subjects/?page_size=100"),
    apiRequest<Paginated<Curriculum>>("/curricula/?page_size=300"),
  ]);

  const sectionChoisie =
    parametres.section ?? String(sections.results[0]?.id ?? "");
  const fasl = await resoudreFasl(fusul.results, parametres.fasl);
  const faslChoisi = String(fasl?.id ?? "");

  const section = sections.results.find((s) => String(s.id) === sectionChoisie);

  const programme = programmes.results
    .filter(
      (p) =>
        String(p.section) === sectionChoisie && String(p.semester) === faslChoisi,
    )
    .sort((a, b) => a.display_order - b.display_order);

  const lien = (modifications: Partial<{ section: string; fasl: string }>) => {
    const params = new URLSearchParams({
      section: modifications.section ?? sectionChoisie,
      fasl: modifications.fasl ?? faslChoisi,
    });
    return `/structure?${params.toString()}`;
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">البنية البيداغوجية</h1>

      <Carte
        titre="الفصول"
        description="حالة كل فصل تحدد من يستطيع الكتابة ومن يستطيع الاطلاع."
        sansPadding
      >
        <ul className="divide-y divide-gray-100">
          {fusul.results.map((f) => (
            <li
              key={f.id}
              className="flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5"
            >
              <div className="min-w-0">
                <p className="font-medium text-dark">
                  الفصل <Nombre>{f.number}</Nombre> — {f.year_label}
                </p>
                <p className="chiffres text-sm text-gris">
                  {f.start_date} → {f.end_date} · الوزن السنوي {f.weight}
                </p>
              </div>
              <BadgeEtat etat={f.state} />
            </li>
          ))}
        </ul>
      </Carte>

      <Carte
        titre={fasl ? `الفصل ${fasl.number} — ${fasl.year_label}` : "البنية"}
        description="يُختار الفصل من الشريط العلوي."
      >
        <div className="space-y-3">
          <Onglets
            libelle="القسم"
            enfants={sections.results.map((s) => (
              <OngletLien
                key={s.id}
                href={lien({ section: String(s.id) })}
                actif={String(s.id) === sectionChoisie}
              >
                {s.name_ar}
              </OngletLien>
            ))}
          />
        </div>
      </Carte>

      {section && fasl ? (
        <GestionProgramme
          section={section}
          fasl={fasl}
          programme={programme}
          matieres={matieres.results}
          verrouille={fasl.state === "PUBLISHED"}
        />
      ) : (
        <Carte>
          <Vide>اختر قسما وفصلا لعرض البرنامج.</Vide>
        </Carte>
      )}

      <CatalogueMatieres matieres={matieres.results} />

      <Carte titre="نظرة شاملة" description="مجموع الضوارب لكل قسم وفصل" sansPadding>
        <div className="overflow-x-auto">
          <table className="data-table min-w-[26rem]">
            <thead>
              <tr>
                <th>القسم</th>
                {fusul.results.map((f) => (
                  <th key={f.id} className="centre">
                    الفصل <Nombre>{f.number}</Nombre>
                  </th>
                ))}
                <th className="fin">الطالبات</th>
              </tr>
            </thead>
            <tbody>
              {sections.results.map((s) => (
                <tr key={s.id}>
                  <td className="font-medium">{s.name_ar}</td>
                  {fusul.results.map((f) => {
                    const lignes = programmes.results.filter(
                      (p) =>
                        p.section === s.id && p.semester === f.id && p.is_active,
                    );
                    const total = lignes.reduce(
                      (somme, p) => somme + Number(p.coefficient),
                      0,
                    );
                    return (
                      <td key={f.id} className="centre">
                        {lignes.length === 0 ? (
                          <span className="text-xs text-gris">—</span>
                        ) : (
                          <>
                            <span className="chiffres font-semibold text-primary">
                              {total}
                            </span>
                            <span className="chiffres block text-[11px] text-gris">
                              {lignes.length} مواد
                            </span>
                          </>
                        )}
                      </td>
                    );
                  })}
                  <td className="fin">
                    <span className="chiffres text-gris">
                      {s.student_count}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Carte>
    </div>
  );
}
