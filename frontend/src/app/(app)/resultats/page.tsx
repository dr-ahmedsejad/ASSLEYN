import { Pagination } from "@/components/Pagination";
import { TableauClassement } from "@/components/TableauClassement";
import { Carte, OngletLien, Onglets, Vide } from "@/components/ui";
import { apiRequest } from "@/lib/api";
import { Refus } from "@/components/Refus";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import { resoudreFasl } from "@/lib/contexte";
import type {
  ExamSession,
  Paginated,
  Section,
  Semester,
  SemesterResult,
} from "@/lib/types";

export const metadata = { title: "النتائج — معهد الأصلين" };

const TAILLE_PAGE = 25;

const SESSIONS: { valeur: ExamSession; libelle: string }[] = [
  { valeur: "NORMAL", libelle: "الدورة العادية" },
  { valeur: "RESIT", libelle: "الدورة الاستدراكية" },
];

export default async function PageResultats({
  searchParams,
}: {
  searchParams: Promise<{
    section?: string;
    fasl?: string;
    session?: string;
    page?: string;
  }>;
}) {
  // Le sidebar masque cette entree sans la permission ; l'URL, elle,
  // se tape a la main.
  if (!(await utilisateurAvec(PERMISSIONS.NOTES_CONSULTER))) {
    return <Refus titre="النتائج" />;
  }

  const parametres = await searchParams;
  const [sections, fusul] = await Promise.all([
    apiRequest<Paginated<Section>>("/sections/?is_active=true"),
    apiRequest<Paginated<Semester>>("/semesters/"),
  ]);

  const sectionChoisie =
    parametres.section ?? String(sections.results[0]?.id ?? "");
  // Le فصل vient du contexte choisi dans la barre du haut, sauf si l'URL en
  // designe un explicitement.
  const fasl = await resoudreFasl(fusul.results, parametres.fasl);
  const faslChoisi = String(fasl?.id ?? "");
  const page = Math.max(1, Number(parametres.page ?? "1") || 1);
  const sessionChoisie = parametres.session ?? fasl?.current_session ?? "NORMAL";

  const resultats =
    sectionChoisie && faslChoisi
      ? await apiRequest<Paginated<SemesterResult>>(
          `/semester-results/?enrollment__section=${sectionChoisie}` +
            `&semester=${faslChoisi}&session=${sessionChoisie}&ordering=rank` +
            `&page=${page}&page_size=${TAILLE_PAGE}`,
        )
      : null;

  const section = sections.results.find((s) => String(s.id) === sectionChoisie);

  const lien = (
    modifications: Partial<{
      section: string;
      fasl: string;
      session: string;
      page: number;
    }>,
  ) => {
    const params = new URLSearchParams({
      section: modifications.section ?? sectionChoisie,
      fasl: modifications.fasl ?? faslChoisi,
      session: modifications.session ?? sessionChoisie,
      page: String(modifications.page ?? 1),
    });
    return `/resultats?${params.toString()}`;
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">النتائج</h1>

      <Carte
        titre={fasl ? `الفصل ${fasl.number} — ${fasl.year_label}` : "النتائج"}
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
          <Onglets
            libelle="الدورة"
            enfants={SESSIONS.map((s) => (
              <OngletLien
                key={s.valeur}
                href={lien({ session: s.valeur })}
                actif={s.valeur === sessionChoisie}
              >
                {s.libelle}
              </OngletLien>
            ))}
          />
        </div>
      </Carte>

      {resultats === null || resultats.results.length === 0 ? (
        <Carte>
          <Vide>لا توجد نتائج محتسبة لهذا الاختيار.</Vide>
        </Carte>
      ) : (
        <TableauClassement
          titre={`${section?.name_ar ?? "النتائج"} — ${
            SESSIONS.find((x) => x.valeur === sessionChoisie)?.libelle ?? ""
          }`}
          resultats={resultats.results}
          pied={
            <Pagination
              page={page}
              count={resultats.count}
              pageSize={TAILLE_PAGE}
              href={(p) => lien({ page: p })}
              unite="طالبة"
            />
          }
        />
      )}
    </div>
  );
}
