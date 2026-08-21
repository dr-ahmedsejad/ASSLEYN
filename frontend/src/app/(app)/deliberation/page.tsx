import {
  ActionsFasl,
  BoutonSurcharge,
  SeuilParSection,
} from "@/components/ActionsDeliberation";
import { Pagination } from "@/components/Pagination";
import { TableauClassement } from "@/components/TableauClassement";
import {
  Alerte,
  BadgeEtat,
  Carte,
  OngletLien,
  Onglets,
  Pastille,
  Vide,
} from "@/components/ui";
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
  SeuilSection,
} from "@/lib/types";

export const metadata = { title: "المداولة — معهد الأصلين" };

const TAILLE_PAGE = 25;

const SESSIONS: { valeur: ExamSession; libelle: string }[] = [
  { valeur: "NORMAL", libelle: "الدورة العادية" },
  { valeur: "RESIT", libelle: "الدورة الاستدراكية" },
];

export default async function PageDeliberation({
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
  if (!(await utilisateurAvec(PERMISSIONS.DELIBERATION_GERER))) {
    return <Refus titre="المداولة" />;
  }

  const parametres = await searchParams;
  const [sections, fusul] = await Promise.all([
    apiRequest<Paginated<Section>>("/sections/?is_active=true"),
    apiRequest<Paginated<Semester>>("/semesters/"),
  ]);

  const sectionChoisie =
    parametres.section ?? String(sections.results[0]?.id ?? "");
  const fasl = await resoudreFasl(fusul.results, parametres.fasl);
  const faslChoisi = String(fasl?.id ?? "");
  const page = Math.max(1, Number(parametres.page ?? "1") || 1);

  const section = sections.results.find((s) => String(s.id) === sectionChoisie);
  const sessionChoisie = parametres.session ?? fasl?.current_session ?? "NORMAL";

  const [resultats, seuils] = await Promise.all([
    sectionChoisie && faslChoisi
      ? apiRequest<Paginated<SemesterResult>>(
          `/semester-results/?enrollment__section=${sectionChoisie}` +
            `&semester=${faslChoisi}&session=${sessionChoisie}&ordering=rank` +
            `&page=${page}&page_size=${TAILLE_PAGE}`,
        )
      : Promise.resolve(null),
    fasl
      ? apiRequest<SeuilSection[]>(`/semesters/${fasl.id}/seuils/`)
      : Promise.resolve([] as SeuilSection[]),
  ]);

  const publie = fasl?.state === "PUBLISHED";
  const sessionAffichee = sessionChoisie === fasl?.current_session;

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
    return `/deliberation?${params.toString()}`;
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">المداولة</h1>

      <Carte
        titre={fasl ? `الفصل ${fasl.number} — ${fasl.year_label}` : "الفصل"}
        description="يُختار الفصل من الشريط العلوي."
        actions={
          fasl ? (
            <div className="flex flex-wrap items-center gap-2">
              <Pastille
                libelle={fasl.current_session_display}
                variante={
                  fasl.current_session === "RESIT" ? "warning" : "info"
                }
                point
              />
              <BadgeEtat etat={fasl.state} />
              <ActionsFasl
                faslId={fasl.id}
                etat={fasl.state}
                session={fasl.current_session}
              />
            </div>
          ) : null
        }
      >
        <div className="space-y-3">
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

        <div className="mt-4">
          <Alerte ton="info">
            القرار المعروض محسوب آليا. يمكن للمجلس تعديله بذكر السبب؛ يبقى
            القرار المحسوب محفوظا إلى جانب القرار المعتمد. بعد النشر لا يمكن
            التعديل إلا بإعادة الفصل إلى حالة «مغلق».
          </Alerte>
        </div>
      </Carte>

      {fasl ? (
        <Carte
          titre="عتبة النجاح لكل قسم"
          description="تُحدد في المداولة، وتخص هذا الفصل وحده. يُعاد الاحتساب فور الحفظ."
          sansPadding
        >
          <div className="px-4 py-4 sm:px-5">
            {publie ? (
              <div className="mb-3">
                <Alerte ton="warning">
                  النتائج منشورة: أعد الفصل إلى حالة «مغلق» لتعديل العتبات.
                </Alerte>
              </div>
            ) : null}
            <SeuilParSection
              faslId={fasl.id}
              seuils={seuils}
              verrouille={publie}
            />
          </div>
        </Carte>
      ) : null}

      {resultats === null || resultats.results.length === 0 ? (
        <Carte>
          <Vide>
            {sessionChoisie === "RESIT"
              ? "لا توجد نتائج للدورة الاستدراكية بعد."
              : "لا توجد نتائج محتسبة لهذا الاختيار."}
          </Vide>
        </Carte>
      ) : (
        <TableauClassement
          titre={`${section?.name_ar ?? "المداولة"} — ${
            SESSIONS.find((s) => s.valeur === sessionChoisie)?.libelle ?? ""
          }`}
          resultats={resultats.results}
          action={(resultat) => (
            <BoutonSurcharge
              resultatId={resultat.id}
              decisionActuelle={resultat.decision_final}
              verrouille={publie || !sessionAffichee}
            />
          )}
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
