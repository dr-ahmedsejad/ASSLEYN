import Link from "next/link";
import { Share2 } from "lucide-react";

import type {
  AnnualResult,
  SemesterResult,
  SubjectResult,
} from "@/lib/types";

import { estEvalue } from "@/lib/evaluation";

import {
  Alerte,
  BadgeDecision,
  Carte,
  DecisionMatiere,
  Nombre,
  Vide,
} from "./ui";

/**
 * Releve d'une etudiante : un bloc par فصل, puis le resultat annuel.
 *
 * Le rang est affiche avec l'effectif — « 3 من 24 » est lisible, « 3 » seul ne
 * dit rien. Le classement nominatif complet n'est en revanche pas expose.
 */
/**
 * Matieres du plus lourd ضارب au plus leger.
 *
 * C'est l'ordre dans lequel une etudiante lit son releve : la matiere qui
 * pese cinq sur quatorze decide de sa moyenne bien plus que celle qui pese
 * trois, et doit donc se presenter la premiere.
 *
 * A ضارب egal, l'ordre du programme est conserve — `sort` est stable, et cet
 * ordre-la est celui que l'etablissement a fixe.
 */
function parCoefficient(matieres: SubjectResult[]): SubjectResult[] {
  return [...matieres].sort(
    (a, b) => Number(b.coefficient) - Number(a.coefficient),
  );
}

export function ReleveEtudiante({
  semestres,
  annuels,
}: {
  semestres: SemesterResult[];
  annuels: AnnualResult[];
}) {
  if (semestres.length === 0) {
    return (
      <Carte titre="نتائجي">
        <Vide>لم تنشر أي نتائج بعد.</Vide>
      </Carte>
    );
  }

  return (
    <div className="space-y-5">
      <Link
        href="/carte"
        className="flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold text-white shadow-card transition-opacity hover:opacity-90"
        style={{ background: "linear-gradient(135deg,#004d24,#006633)" }}
      >
        <Share2 size={16} />
        بطاقة النتيجة للمشاركة
      </Link>

      {semestres.map((resultat) =>
        !estEvalue(resultat) ? (
          /* Un فصل publie avant la saisie des notes rend une moyenne de 0,00
             et un استدراك que rien ne distingue d'un echec reel. On dit ce
             qu'il en est plutot que d'afficher des chiffres qui ne reposent
             sur rien. */
          <Carte
            key={resultat.id}
            titre={`الفصل ${resultat.semester_number}`}
            description={resultat.section_name}
          >
            <Alerte ton="info">
              لم تُدخل نقاط هذا الفصل بعد. ستظهر النتيجة هنا فور إدخالها
              واعتماد المداولة.
            </Alerte>
          </Carte>
        ) : (
        <Carte
          key={resultat.id}
          titre={`الفصل ${resultat.semester_number}`}
          description={resultat.section_name}
          actions={
            <BadgeDecision
              decision={resultat.decision_final}
              surcharge={resultat.is_overridden}
            />
          }
          sansPadding
        >
          <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 sm:p-5">
            <Statistique
              libelle="المعدل"
              valeur={resultat.average_display}
              accentue
            />
            <Statistique
              libelle="الرتبة"
              valeur={`${resultat.rank} / ${resultat.cohort_size}`}
            />
            <Statistique
              libelle="مجموع الضوارب"
              valeur={resultat.total_coefficient}
            />
          </div>

          <div className="overflow-x-auto border-t border-gray-100">
            <table className="data-table min-w-[26rem]">
              <thead>
                <tr>
                  <th>المادة</th>
                  <th className="centre">الضارب</th>
                  <th className="centre">النقطة</th>
                  <th className="fin">قرار اللجنة</th>
                </tr>
              </thead>
              <tbody>
                {parCoefficient(resultat.subject_results).map((matiere) => (
                  <tr key={matiere.subject_code}>
                    <td className="font-medium">{matiere.subject_name}</td>
                    <td className="centre">
                      <Nombre>{matiere.coefficient}</Nombre>
                    </td>
                    <td className="centre">
                      {matiere.value === null ? (
                        <span className="text-xs text-gris">غائبة</span>
                      ) : (
                        <span className="chiffres font-semibold">
                          {matiere.value}
                        </span>
                      )}
                    </td>
                    <td className="fin">
                      <DecisionMatiere code={matiere.decision} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {resultat.is_overridden && resultat.override_reason ? (
            <p className="border-t border-gray-100 bg-yellow-50 px-4 py-3 text-xs text-yellow-700 sm:px-5">
              قرار اللجنة: {resultat.override_reason}
            </p>
          ) : null}
        </Carte>
        )
      )}

      {annuels.map((annuel) => (
        <Carte
          key={annuel.id}
          titre="النتيجة السنوية"
          description={`معدل الفصلين · ${annuel.semester_count} من 2 محتسب`}
          actions={<BadgeDecision decision={annuel.decision_final} />}
        >
          <div className="grid grid-cols-2 gap-3">
            <Statistique
              libelle="المعدل السنوي"
              valeur={annuel.average_display}
              accentue
            />
            <Statistique
              libelle="الرتبة السنوية"
              valeur={`${annuel.rank} / ${annuel.cohort_size}`}
            />
          </div>
        </Carte>
      ))}
    </div>
  );
}

function Statistique({
  libelle,
  valeur,
  accentue,
}: {
  libelle: string;
  valeur: string;
  accentue?: boolean;
}) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 px-3.5 py-3">
      <p className="text-xs text-gris">{libelle}</p>
      <p
        className={`chiffres mt-0.5 font-semibold ${
          accentue ? "text-2xl text-primary" : "text-base text-dark"
        }`}
      >
        {valeur}
      </p>
    </div>
  );
}
