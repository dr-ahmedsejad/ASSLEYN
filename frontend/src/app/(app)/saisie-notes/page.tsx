import { GrilleNotes } from "@/components/GrilleNotes";
import { Refus } from "@/components/Refus";
import { SelecteurMatiere } from "@/components/SelecteurMatiere";
import { Alerte, Carte, OngletLien, Onglets, Pastille } from "@/components/ui";
import { ApiError, apiRequest } from "@/lib/api";
import { utilisateurAvec } from "@/lib/acces";
import { resoudreFasl } from "@/lib/contexte";
import { PERMISSIONS } from "@/lib/nav-config";
import type {
  AvancementSaisie,
  Curriculum,
  ExamSession,
  GradeSheet,
  Paginated,
  Semester,
} from "@/lib/types";

export const metadata = { title: "إدخال النقاط — معهد الأصلين" };

const SESSIONS: { valeur: ExamSession; libelle: string }[] = [
  { valeur: "NORMAL", libelle: "الدورة العادية" },
  { valeur: "RESIT", libelle: "الدورة الاستدراكية" },
];

/**
 * Poste de saisie des notes.
 *
 * Deux listes deroulantes liees — la classe, puis sa matiere — et la grille
 * en dessous. Chaque option porte son avancement, ce qui evite d'empiler un
 * sommaire ou une barre de navigation par-dessus. Un enseignant y retrouve la
 * meme chose, reduite aux matieres qu'il enseigne.
 */
export default async function PageSaisie({
  searchParams,
}: {
  searchParams: Promise<{
    curriculum?: string;
    section?: string;
    session?: string;
  }>;
}) {
  // Le sidebar masque cette entree sans la permission ; l'URL, elle, se tape
  // a la main.
  if (!(await utilisateurAvec(PERMISSIONS.NOTES_SAISIR))) {
    return <Refus titre="إدخال النقاط" />;
  }

  const {
    curriculum: choisi,
    section: sectionUrl,
    session,
  } = await searchParams;

  const fusul = await apiRequest<Paginated<Semester>>("/semesters/");

  // Une matiere designee dans l'URL commande le فصل affiche : c'est la meme
  // regle que partout ailleurs — un lien explicite prime sur le contexte.
  // Sans cela, ouvrir le lien d'une matiere d'un autre فصل n'affichait rien.
  const matiereDemandee = choisi
    ? await apiRequest<Curriculum>(
        `/curricula/${encodeURIComponent(choisi)}/`,
      ).catch(() => null)
    : null;

  const fasl = await resoudreFasl(
    fusul.results,
    matiereDemandee ? String(matiereDemandee.semester) : undefined,
  );

  if (!fasl) {
    return (
      <div className="space-y-5">
        <h1 className="text-xl font-bold text-dark">إدخال النقاط</h1>
        <Carte>
          <Alerte ton="warning">لا يوجد فصل دراسي بعد.</Alerte>
        </Carte>
      </div>
    );
  }

  const sessionChoisie = session ?? fasl.current_session;

  const avancement = await apiRequest<AvancementSaisie>(
    `/grading/avancement/?semester=${fasl.id}&session=${encodeURIComponent(
      sessionChoisie,
    )}`,
  );

  // La matiere doit figurer dans l'avancement : elle peut exister mais etre
  // desactivee, ou hors du perimetre d'un enseignant.
  const identifiant = choisi ? Number(choisi) : null;
  const matiere = avancement.sections
    .flatMap((s) => s.matieres)
    .find((m) => m.curriculum === identifiant);

  // La classe suit la matiere ouverte ; a defaut celle de l'URL, puis la
  // premiere de la liste.
  const sectionCourante =
    avancement.sections.find((s) =>
      s.matieres.some((m) => m.curriculum === identifiant),
    )?.id ??
    (sectionUrl ? Number(sectionUrl) : null) ??
    avancement.sections[0]?.id ??
    null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-dark">إدخال النقاط</h1>
        <Onglets
          libelle="الدورة"
          enfants={SESSIONS.map((s) => (
            <OngletLien
              key={s.valeur}
              href={`/saisie-notes?session=${s.valeur}`}
              actif={s.valeur === sessionChoisie}
            >
              {s.libelle}
              {s.valeur === fasl.current_session ? (
                <span className="ms-1.5 text-[10px] font-semibold text-primary">
                  (الجارية)
                </span>
              ) : null}
            </OngletLien>
          ))}
        />
      </div>

      <Carte
        titre={`الفصل ${fasl.number} — ${fasl.year_label}`}
        description="اختر القسم ثم المادة."
        actions={
          <Pastille
            libelle={avancement.semester.state_display}
            variante={avancement.semester.editable ? "info" : "warning"}
            point
          />
        }
      >
        <SelecteurMatiere
          avancement={avancement}
          sectionChoisie={sectionCourante}
          matiereChoisie={matiere?.curriculum ?? null}
        />
      </Carte>

      {identifiant && !matiere ? (
        <Carte>
          <Alerte ton="warning">
            المادة المطلوبة غير متاحة لك في هذه الدورة. اختر مادة من القائمة
            أعلاه.
          </Alerte>
        </Carte>
      ) : null}

      {matiere ? (
        <Grille
          curriculumId={String(matiere.curriculum)}
          session={sessionChoisie}
        />
      ) : null}
    </div>
  );
}

async function Grille({
  curriculumId,
  session,
}: {
  curriculumId: string;
  session: string;
}) {
  let feuille: GradeSheet;
  try {
    feuille = await apiRequest<GradeSheet>(
      `/grading/sheet/?curriculum=${encodeURIComponent(curriculumId)}` +
        `&session=${encodeURIComponent(session)}`,
    );
  } catch (erreur) {
    const message =
      erreur instanceof ApiError
        ? (erreur.messages[0] ?? "تعذر تحميل الجدول.")
        : "تعذر تحميل الجدول.";
    return (
      <Carte>
        <Alerte ton="danger">{message}</Alerte>
      </Carte>
    );
  }

  return <GrilleNotes feuille={feuille} />;
}
