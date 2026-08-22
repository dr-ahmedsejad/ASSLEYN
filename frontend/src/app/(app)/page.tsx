import Link from "next/link";
import { redirect } from "next/navigation";
import {
  BookOpenCheck,
  CalendarRange,
  ChevronLeft,
  GraduationCap,
  Layers,
  Users,
} from "lucide-react";

import { ReleveEtudiante } from "@/components/ReleveEtudiante";
import {
  Alerte,
  BadgeEtat,
  Carte,
  Indicateur,
  Nombre,
  Vide,
} from "@/components/ui";
import { apiRequest, getCurrentUser } from "@/lib/api";
import { pageDAtterrissage } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type {
  AnnualResult,
  Curriculum,
  Paginated,
  Section,
  Semester,
  SemesterResult,
} from "@/lib/types";

export const metadata = { title: "الرئيسية — معهد الأصلين" };

export default async function PageAccueil() {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) return null;

  // Quelle version du tableau de bord afficher depend de **qui** est la
  // personne, pas d'un droit : l'administration possede toutes les
  // permissions, `resultats.personnels` comprise, et n'a pourtant pas de
  // releve personnel a consulter.
  if (utilisateur.role === "STUDENT") return <AccueilEtudiante />;

  // Sans droit au tableau de bord, la racine n'a rien a montrer : on renvoie
  // la personne sur son ecran de travail plutot que sur une page vide.
  if (!utilisateur.permissions.includes(PERMISSIONS.TABLEAU_CONSULTER)) {
    const destination = pageDAtterrissage(utilisateur);
    redirect(destination === "/" ? "/mot-de-passe" : destination);
  }

  if (utilisateur.role === "TEACHER") return <AccueilEnseignant />;
  return <AccueilAdministration />;
}

/* ------------------------------------------------------------------ */

async function AccueilEtudiante() {
  // Le releve ne contient que les فصول **publies** : un فصل en cours de
  // saisie ne doit pas fuiter. L'absence, seule, laisse une etudiante devant
  // un ecran qui ne montre qu'un فصل sans lui dire pourquoi — on nomme donc
  // ceux qui restent a venir.
  const [releve, fusul] = await Promise.all([
    apiRequest<{ semesters: SemesterResult[]; annual: AnnualResult[] }>(
      "/results/me/",
    ),
    apiRequest<Paginated<Semester>>("/semesters/").catch(() => null),
  ]);

  const publies = new Set(releve.semesters.map((s) => s.semester_number));
  const aVenir = (fusul?.results ?? [])
    .filter((f) => f.state !== "PUBLISHED" && !publies.has(f.number))
    .map((f) => f.number)
    .sort();

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">نتائجي</h1>

      <ReleveEtudiante semestres={releve.semesters} annuels={releve.annual} />

      {aVenir.length > 0 ? (
        <Alerte ton="info">
          {aVenir.length === 1 ? "الفصل" : "الفصول"}{" "}
          <span className="chiffres font-semibold">{aVenir.join(" و ")}</span>{" "}
          لم {aVenir.length === 1 ? "يُنشر" : "تُنشر"} بعد. ستظهر النتيجة هنا
          فور اعتمادها من الإدارة.
        </Alerte>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */

async function AccueilEnseignant() {
  const matieres = await apiRequest<Paginated<Curriculum>>(
    "/curricula/?is_active=true",
  );

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">موادي</h1>

      <div className="grid gap-4 sm:grid-cols-2">
        <Indicateur
          libelle="المواد المسندة"
          valeur={matieres.count}
          icone={<BookOpenCheck size={17} />}
        />
      </div>

      <Carte
        titre="المواد المسندة إليك"
        description="اختر مادة لإدخال نقاطها."
        sansPadding
      >
        {matieres.results.length === 0 ? (
          <div className="p-4 sm:p-5">
            <Vide>لا توجد مواد مسندة إليك حاليا.</Vide>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {matieres.results.map((matiere) => (
              <li key={matiere.id}>
                <Link
                  href={`/saisie-notes?curriculum=${matiere.id}`}
                  className="flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5 transition-colors hover:bg-gray-50"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-dark">
                      {matiere.subject_name}
                    </p>
                    <p className="text-sm text-gris">
                      {matiere.section_name} · الفصل{" "}
                      <Nombre>{matiere.semester_number}</Nombre> · الضارب{" "}
                      <Nombre>{matiere.coefficient}</Nombre>
                    </p>
                  </div>
                  <span className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary">
                    إدخال النقاط
                    <ChevronLeft size={15} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Carte>
    </div>
  );
}

/* ------------------------------------------------------------------ */

async function AccueilAdministration() {
  const [sections, fusul, matieres] = await Promise.all([
    apiRequest<Paginated<Section>>("/sections/?is_active=true"),
    apiRequest<Paginated<Semester>>("/semesters/"),
    apiRequest<Paginated<Curriculum>>("/curricula/?is_active=true&page_size=1"),
  ]);

  const effectif = sections.results.reduce(
    (total, section) => total + section.student_count,
    0,
  );
  const faslCourant =
    fusul.results.find((f) => f.state === "OPEN") ??
    fusul.results.find((f) => f.state === "CLOSED") ??
    fusul.results[0];

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">لوحة القيادة</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Indicateur
          libelle="الأقسام"
          valeur={sections.results.length}
          icone={<Layers size={17} />}
        />
        <Indicateur
          libelle="الطالبات"
          valeur={effectif}
          icone={<Users size={17} />}
        />
        <Indicateur
          libelle="مواد الفصول"
          valeur={matieres.count}
          icone={<BookOpenCheck size={17} />}
        />
        <Indicateur
          libelle="الفصل الجاري"
          valeur={faslCourant ? faslCourant.number : "—"}
          detail={faslCourant?.state_display}
          icone={<CalendarRange size={17} />}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Carte titre="الفصول الدراسية" sansPadding>
          {fusul.results.length === 0 ? (
            <div className="p-4 sm:p-5">
              <Vide>لم تنشأ أي فصول بعد.</Vide>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {fusul.results.map((fasl) => (
                <li
                  key={fasl.id}
                  className="flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-dark">
                      الفصل <Nombre>{fasl.number}</Nombre>
                    </p>
                    <p className="chiffres text-sm text-gris">
                      {fasl.year_label} · {fasl.start_date} → {fasl.end_date}
                    </p>
                  </div>
                  <BadgeEtat etat={fasl.state} />
                </li>
              ))}
            </ul>
          )}
        </Carte>

        <Carte titre="الأقسام" sansPadding>
          <ul className="divide-y divide-gray-100">
            {sections.results.map((section) => (
              <li key={section.id}>
                <Link
                  href={`/resultats?section=${section.id}`}
                  className="flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5 transition-colors hover:bg-gray-50"
                >
                  <span className="flex items-center gap-2.5 font-medium text-dark">
                    <GraduationCap size={16} className="text-gris" />
                    {section.name_ar}
                  </span>
                  <span className="chiffres text-sm text-gris">
                    {section.student_count} طالبة
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Carte>
      </div>
    </div>
  );
}
