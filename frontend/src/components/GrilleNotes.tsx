"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";

import type { GradeRow, GradeSheet, GradeStatus } from "@/lib/types";

import { Alerte, BadgeEtat, BarreProgression, Carte, Pastille } from "./ui";

/**
 * Grille de saisie des notes.
 *
 * Les enseignants viennent d'Excel : la navigation clavier doit etre au moins
 * aussi rapide. Entree et Flèche bas passent a la ligne suivante, Flèche haut
 * remonte. La note est validee localement pendant la frappe, et le lot entier
 * n'est envoye qu'au moment de l'enregistrement — tout ou rien.
 *
 * En session de rattrapage, la grille ne contient que les etudiantes
 * convoquees dans cette matiere, et rappelle leur note de session normale :
 * c'est elle que le rattrapage doit ameliorer.
 *
 * Cette grille n'est volontairement **pas paginee** : une colonne de notes se
 * saisit d'un bloc, et une pagination ferait perdre les lignes modifiees non
 * encore enregistrees a chaque changement de page.
 */

interface Ligne extends GradeRow {
  saisie: string;
}

function texte(valeur: string | number | null | undefined): string {
  return valeur === null || valeur === undefined ? "" : String(valeur);
}

function versLigne(row: GradeRow): Ligne {
  return {
    ...row,
    // « Pas encore saisie » n'est pas un etat que l'on choisit : c'est
    // l'absence de decision. On l'affiche donc comme une note a saisir, sans
    // quoi le champ d'une matiere vierge naissait desactive et la grille
    // paraissait inerte.
    status: row.status === "MISSING" ? "ENTERED" : row.status,
    // L'API peut renvoyer un decimal en chaine ou en nombre selon la route :
    // on normalise ici plutot que de supposer un type a chaque usage.
    saisie: texte(row.value),
  };
}

export function GrilleNotes({ feuille }: { feuille: GradeSheet }) {
  const router = useRouter();
  const noteMax = Number(feuille.max_grade);
  const rattrapage = feuille.session === "RESIT";

  const [lignes, setLignes] = useState<Ligne[]>(() =>
    feuille.rows.map(versLigne),
  );
  const [initiales] = useState<Ligne[]>(() => feuille.rows.map(versLigne));
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<{
    type: "succes" | "danger";
    texte: string;
  } | null>(null);

  const champs = useRef<(HTMLInputElement | null)[]>([]);

  const erreurs = useMemo(() => {
    const trouvees = new Map<number, string>();
    lignes.forEach((ligne, index) => {
      if (ligne.saisie.trim() === "") return;
      const valeur = Number(ligne.saisie.replace(",", "."));
      if (Number.isNaN(valeur)) {
        trouvees.set(index, "قيمة غير رقمية");
      } else if (valeur < 0 || valeur > noteMax) {
        trouvees.set(index, `بين 0 و ${noteMax}`);
      }
    });
    return trouvees;
  }, [lignes, noteMax]);

  const modifiees = useMemo(
    () =>
      lignes.filter((ligne, index) => ligne.saisie !== initiales[index].saisie),
    [lignes, initiales],
  );

  const saisies = lignes.filter((ligne) => ligne.saisie.trim() !== "").length;

  function majLigne(index: number, patch: Partial<Ligne>) {
    setLignes((precedent) =>
      precedent.map((ligne, i) =>
        i === index ? { ...ligne, ...patch } : ligne,
      ),
    );
    setMessage(null);
  }

  function surTouche(event: React.KeyboardEvent, index: number) {
    if (event.key === "Enter" || event.key === "ArrowDown") {
      event.preventDefault();
      champs.current[index + 1]?.focus();
      champs.current[index + 1]?.select();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      champs.current[index - 1]?.focus();
      champs.current[index - 1]?.select();
    }
  }

  async function enregistrer() {
    if (erreurs.size > 0 || modifiees.length === 0) return;
    setEnCours(true);
    setMessage(null);

    // Une case laissee vide vaut zero : c'est la regle de l'institut, et
    // c'est ce que faisait deja le fichier d'origine. Seules les lignes
    // reellement touchees partent, donc une matiere a peine ouverte ne se
    // remplit pas de zeros toute seule.
    const charge = modifiees.map((ligne) => ({
      enrollment: ligne.enrollment,
      status: "ENTERED" as GradeStatus,
      value: ligne.saisie.trim() === "" ? 0 : Number(ligne.saisie.replace(",", ".")),
    }));

    try {
      const reponse = await fetch("/api/bff/grading/sheet/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          curriculum: feuille.curriculum.id,
          grades: charge,
        }),
      });

      if (!reponse.ok) {
        const corps = await reponse.json().catch(() => null);
        setMessage({
          type: "danger",
          texte: extraireMessage(corps) ?? "تعذر حفظ النقاط.",
        });
        return;
      }

      const resultat = await reponse.json();
      setMessage({
        type: "succes",
        texte: `تم حفظ ${resultat.modifiees} نقطة، وأعيد احتساب ${resultat.etudiantes_recalculees} طالبة.`,
      });
      router.refresh();
    } catch {
      setMessage({ type: "danger", texte: "تعذر الاتصال بالخادم." });
    } finally {
      setEnCours(false);
    }
  }

  const modifiable = feuille.curriculum.editable;

  return (
    <Carte
      titre={`${feuille.curriculum.subject_name} — ${feuille.curriculum.section_name}`}
      description={`الفصل ${feuille.curriculum.semester_number} · الضارب ${feuille.curriculum.coefficient} · النقطة القصوى ${feuille.max_grade}`}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Pastille
            libelle={feuille.session_display}
            variante={rattrapage ? "warning" : "info"}
            point
          />
          <BadgeEtat etat={feuille.curriculum.semester_state} />
        </div>
      }
      sansPadding
    >
      <div className="space-y-3 px-4 py-4 sm:px-5">
        {rattrapage ? (
          <Alerte ton="warning">
            الدورة الاستدراكية: لا تظهر إلا الطالبات المعنيات بهذه المادة.
            تُعتمد أعلى النقطتين، فلا يمكن أن تخسر الطالبة نقاطا بإعادة الامتحان.
          </Alerte>
        ) : null}

        {!modifiable ? (
          <Alerte ton="warning">
            {feuille.session === feuille.current_session
              ? "الفصل غير مفتوح للإدخال. الجدول معروض للاطلاع فقط."
              : "هذه الدورة ليست الدورة الجارية. الجدول معروض للاطلاع فقط."}
          </Alerte>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <BarreProgression fait={saisies} total={lignes.length} />
          <div className="flex flex-wrap items-center gap-3">
            {modifiees.length > 0 ? (
              <span className="chiffres text-xs font-medium text-yellow-700">
                {modifiees.length} تعديل غير محفوظ
              </span>
            ) : null}
            <BoutonEnregistrer
              onClick={enregistrer}
              desactive={
                !modifiable ||
                enCours ||
                modifiees.length === 0 ||
                erreurs.size > 0
              }
              enCours={enCours}
            />
          </div>
        </div>

        {message ? (
          <Alerte ton={message.type === "succes" ? "succes" : "danger"}>
            {message.texte}
          </Alerte>
        ) : null}
      </div>

      {lignes.length === 0 ? (
        <p className="border-t border-gray-100 py-10 text-center text-sm text-gris">
          لا توجد طالبة معنية بالدورة الاستدراكية في هذه المادة.
        </p>
      ) : (
        <div className="border-t border-gray-100">
          {/* En-tetes : inutiles sur mobile, ou chaque ligne se lit seule. */}
          <div
            className={`hidden gap-3 border-b border-gray-100 bg-gray-50 px-4 py-2.5 text-xs font-semibold text-gris sm:grid sm:px-5 ${
              rattrapage
                ? "sm:grid-cols-[6rem_1fr_6rem_8rem]"
                : "sm:grid-cols-[6rem_1fr_8rem]"
            }`}
          >
            <span>رقم الطالبة</span>
            <span>الاسم الكامل</span>
            {rattrapage ? (
              <span className="text-center">الدورة العادية</span>
            ) : null}
            <span className="text-center">النقطة</span>
          </div>

          <ul className="divide-y divide-gray-100">
            {lignes.map((ligne, index) => {
              const erreur = erreurs.get(index);
              return (
                <li
                  key={ligne.enrollment}
                  className={`grid items-center gap-x-3 gap-y-1 px-4 py-3 transition-colors hover:bg-gray-50 sm:px-5 sm:py-2.5 ${
                    rattrapage
                      ? "grid-cols-[1fr_5.5rem] sm:grid-cols-[6rem_1fr_6rem_8rem]"
                      : "grid-cols-[1fr_5.5rem] sm:grid-cols-[6rem_1fr_8rem]"
                  }`}
                >
                  {/* Mobile : matricule et nom empiles dans la meme colonne.
                      A partir de `sm`, chacun reprend la sienne. */}
                  <span className="order-2 col-start-1 row-start-2 sm:order-none sm:col-start-auto sm:row-start-auto">
                    <span className="chiffres text-xs text-gris">
                      {ligne.matricule}
                    </span>
                    {rattrapage ? (
                      <span className="chiffres ms-2 text-xs text-gris sm:hidden">
                        · الدورة العادية {texte(ligne.normal_value) || "—"}
                      </span>
                    ) : null}
                  </span>

                  <span className="order-1 col-start-1 row-start-1 truncate text-sm font-medium text-dark sm:order-none sm:col-start-auto sm:row-start-auto">
                    {ligne.full_name_ar}
                  </span>

                  {rattrapage ? (
                    <span className="hidden text-center sm:block">
                      <span className="chiffres text-gris">
                        {texte(ligne.normal_value) || "—"}
                      </span>
                    </span>
                  ) : null}

                  <span className="col-start-2 row-span-2 row-start-1 sm:col-start-auto sm:row-span-1 sm:row-start-auto">
                    <input
                      ref={(element) => {
                        champs.current[index] = element;
                      }}
                      type="text"
                      inputMode="decimal"
                      className="champ-note"
                      value={ligne.saisie}
                      disabled={!modifiable}
                      aria-label={`نقطة ${ligne.full_name_ar}`}
                      aria-invalid={erreur ? true : undefined}
                      onChange={(event) =>
                        majLigne(index, { saisie: event.target.value })
                      }
                      onKeyDown={(event) => surTouche(event, index)}
                      style={erreur ? { borderColor: "#ef4444" } : undefined}
                    />
                    {erreur ? (
                      <span className="mt-1 block text-center text-[11px] text-red-600">
                        {erreur}
                      </span>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {lignes.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 px-4 py-4 sm:px-5">
          <span className="chiffres text-xs text-gris">
            {saisies} / {lignes.length}
            {modifiees.length > 0 ? (
              <span className="ms-2 font-medium text-yellow-700">
                {modifiees.length} تعديل غير محفوظ
              </span>
            ) : null}
          </span>
          <BoutonEnregistrer
            onClick={enregistrer}
            desactive={
              !modifiable || enCours || modifiees.length === 0 || erreurs.size > 0
            }
            enCours={enCours}
          />
        </div>
      ) : null}

      <p className="border-t border-gray-100 px-4 py-3 text-xs text-gris sm:px-5">
        اضغط «Enter» أو السهم لأسفل للانتقال إلى الطالبة التالية. النقطة
        الفارغة تُحتسب صفرا.
      </p>
    </Carte>
  );
}

function BoutonEnregistrer({
  onClick,
  desactive,
  enCours,
}: {
  onClick: () => void;
  desactive: boolean;
  enCours: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={desactive}
      className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 sm:py-2"
      style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
    >
      <Save size={15} />
      {enCours ? "جارٍ الحفظ…" : "حفظ"}
    </button>
  );
}

function extraireMessage(corps: unknown): string | null {
  if (!corps || typeof corps !== "object") return null;
  for (const valeur of Object.values(corps as Record<string, unknown>)) {
    if (Array.isArray(valeur) && valeur.length > 0) return String(valeur[0]);
    if (typeof valeur === "string") return valeur;
  }
  return null;
}
