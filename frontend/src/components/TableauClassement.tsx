import type { SemesterResult } from "@/lib/types";

import { BadgeDecision, Carte, DecisionMatiere, Nombre } from "./ui";

/**
 * Classement d'une section pour un فصل.
 *
 * Les matieres sont deduites de la premiere ligne : dans une section donnee,
 * toutes les etudiantes suivent le meme programme.
 */
export function TableauClassement({
  titre,
  resultats,
  action,
  pied,
}: {
  titre: string;
  resultats: SemesterResult[];
  action?: (resultat: SemesterResult) => React.ReactNode;
  pied?: React.ReactNode;
}) {
  const matieres = resultats[0]?.subject_results ?? [];
  const reussites = resultats.filter(
    (r) => r.decision_final === "PASSED",
  ).length;

  return (
    <Carte
      titre={titre}
      description={`${resultats.length} طالبة معروضة · ${reussites} ناجحة · ${
        resultats.length - reussites
      } استدراك`}
      sansPadding
    >
      <div className="overflow-x-auto">
        <table className="data-table min-w-[48rem]">
          <thead>
            <tr>
              <th className="centre">الرتبة</th>
              <th>رقم الطالبة</th>
              <th>الاسم الكامل</th>
              {matieres.map((matiere) => (
                <th key={matiere.subject_code} className="centre">
                  {matiere.subject_name}
                  <span className="chiffres block text-[10px] font-normal opacity-70">
                    ض {matiere.coefficient}
                  </span>
                </th>
              ))}
              <th className="centre">المعدل</th>
              <th className="fin">قرار اللجنة</th>
              {action ? <th className="fin" /> : null}
            </tr>
          </thead>
          <tbody>
            {resultats.map((resultat) => (
              <tr key={resultat.id}>
                <td className="centre">
                  <span className="chiffres font-bold text-primary">
                    {resultat.rank}
                  </span>
                </td>
                <td>
                  <span className="chiffres text-gris">
                    {resultat.matricule}
                  </span>
                </td>
                <td className="font-medium">{resultat.full_name_ar}</td>
                {resultat.subject_results.map((matiere) => (
                  <td key={matiere.subject_code} className="centre">
                    {matiere.value === null ? (
                      <span className="text-[11px] text-gris">غ</span>
                    ) : (
                      <Nombre>{matiere.value}</Nombre>
                    )}
                    <span className="block">
                      <DecisionMatiere code={matiere.decision} />
                    </span>
                  </td>
                ))}
                <td className="centre">
                  <span className="chiffres font-semibold text-dark">
                    {resultat.average_display}
                  </span>
                </td>
                <td className="fin">
                  <BadgeDecision
                    decision={resultat.decision_final}
                    surcharge={resultat.is_overridden}
                  />
                </td>
                {action ? <td className="fin">{action(resultat)}</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pied ? <div className="px-4 pb-4 sm:px-5 sm:pb-5">{pied}</div> : null}
    </Carte>
  );
}
