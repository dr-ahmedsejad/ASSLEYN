"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import type { OverallDecision, SemesterState, SeuilSection } from "@/lib/types";

async function appeler(chemin: string, corps?: unknown) {
  const reponse = await fetch(`/api/bff/${chemin}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
  if (!reponse.ok) {
    const payload = await reponse.json().catch(() => null);
    throw new Error(premierMessage(payload) ?? "تعذر تنفيذ العملية.");
  }
  return reponse.json().catch(() => null);
}

function premierMessage(corps: unknown): string | null {
  if (typeof corps === "string") return corps;
  if (!corps || typeof corps !== "object") return null;
  for (const valeur of Object.values(corps as Record<string, unknown>)) {
    if (Array.isArray(valeur) && valeur.length > 0) return String(valeur[0]);
    if (typeof valeur === "string") return valeur;
  }
  return null;
}

/**
 * Transitions d'etat d'un فصل.
 *
 * L'ouverture de la session de rattrapage n'est pas une transition d'etat
 * comme les autres : elle fait repasser le فصل en saisie **dans la seconde
 * session**, sans toucher aux notes de la premiere.
 */
export function ActionsFasl({
  faslId,
  etat,
  session,
}: {
  faslId: number;
  etat: SemesterState;
  session: "NORMAL" | "RESIT";
}) {
  const router = useRouter();
  const [enCours, setEnCours] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  async function executer(operation: string) {
    setEnCours(operation);
    setErreur(null);
    try {
      await appeler(`semesters/${faslId}/${operation}`);
      router.refresh();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : "خطأ غير متوقع.");
    } finally {
      setEnCours(null);
    }
  }

  const boutons: { cle: string; libelle: string; accent?: boolean }[] = [];
  if (etat === "DRAFT") boutons.push({ cle: "open", libelle: "فتح الإدخال" });
  if (etat === "OPEN") boutons.push({ cle: "close", libelle: "إغلاق واحتساب" });
  if (etat === "CLOSED") {
    boutons.push({ cle: "publish", libelle: "نشر النتائج", accent: true });
    boutons.push({ cle: "open", libelle: "إعادة فتح الإدخال" });
  }
  if (etat === "PUBLISHED") {
    if (session === "NORMAL") {
      boutons.push({
        cle: "open-resit",
        libelle: "فتح الدورة الاستدراكية",
        accent: true,
      });
    }
    boutons.push({ cle: "close", libelle: "إلغاء النشر" });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {boutons.map((bouton) => (
        <button
          key={bouton.cle}
          type="button"
          onClick={() => executer(bouton.cle)}
          disabled={enCours !== null}
          className={
            bouton.accent
              ? "rounded-xl px-3 py-1.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              : "rounded-xl border border-primary px-3 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-green-50 disabled:opacity-50"
          }
          style={
            bouton.accent
              ? { background: "linear-gradient(135deg,#006633,#008844)" }
              : undefined
          }
        >
          {enCours === bouton.cle ? "…" : bouton.libelle}
        </button>
      ))}
      {erreur ? (
        <span className="w-full text-xs text-red-600 sm:w-auto">{erreur}</span>
      ) : null}
    </div>
  );
}

/**
 * Seuils arretes en deliberation, قسم par قسم.
 *
 * Deux valeurs : la barre de reussite, et le plancher de compensation en
 * dessous duquel une note reste eliminatoire quelle que soit la moyenne. Le
 * plancher ne peut pas depasser la barre — la contrainte est verifiee ici et
 * refusee par le serveur.
 *
 * Les seuils ne valent que pour ce فصل et ce قسم. Une nouvelle version du
 * reglement est creee a chaque decision, et la section est recalculee dans la
 * foulee : la commission voit immediatement l'effet de son choix.
 */
export function SeuilParSection({
  faslId,
  seuils,
  verrouille,
}: {
  faslId: number;
  seuils: SeuilSection[];
  verrouille: boolean;
}) {
  const router = useRouter();
  const [barres, setBarres] = useState<Record<number, string>>({});
  const [planchers, setPlanchers] = useState<Record<number, string>>({});
  const [motifs, setMotifs] = useState<Record<number, string>>({});
  const [enCours, setEnCours] = useState<number | null>(null);
  const [message, setMessage] = useState<{
    ton: "succes" | "danger";
    texte: string;
  } | null>(null);

  async function enregistrer(seuil: SeuilSection) {
    const barre = (barres[seuil.section] ?? seuil.pass_threshold).replace(
      ",",
      ".",
    );
    const plancher = (
      planchers[seuil.section] ?? seuil.compensation_floor
    ).replace(",", ".");

    if (Number.isNaN(Number(barre)) || Number(barre) <= 0) {
      setMessage({
        ton: "danger",
        texte: "عتبة النجاح يجب أن تكون رقما أكبر من صفر.",
      });
      return;
    }
    if (Number.isNaN(Number(plancher)) || Number(plancher) < 0) {
      setMessage({
        ton: "danger",
        texte: "الحد الأدنى للتعويض يجب أن يكون رقما موجبا.",
      });
      return;
    }
    // Le serveur refuse aussi ce cas ; le dire ici evite un aller-retour.
    if (Number(plancher) > Number(barre)) {
      setMessage({
        ton: "danger",
        texte: "الحد الأدنى للتعويض لا يمكن أن يتجاوز عتبة النجاح.",
      });
      return;
    }

    setEnCours(seuil.section);
    setMessage(null);
    try {
      const resultat = await appeler(`semesters/${faslId}/seuil`, {
        section: seuil.section,
        pass_threshold: barre,
        compensation_floor: plancher,
        note: (motifs[seuil.section] ?? "").trim(),
      });
      setMessage({
        ton: "succes",
        texte:
          `تم ضبط ${seuil.section_name}: عتبة النجاح ${resultat?.pass_threshold}` +
          ` والحد الأدنى للتعويض ${resultat?.compensation_floor}.` +
          ` أعيد احتساب ${resultat?.etudiantes_recalculees} طالبة.`,
      });
      router.refresh();
    } catch (e) {
      setMessage({
        ton: "danger",
        texte: e instanceof Error ? e.message : "خطأ غير متوقع.",
      });
    } finally {
      setEnCours(null);
    }
  }

  return (
    <div className="space-y-3">
      {message ? (
        <p
          role="status"
          className={`rounded-xl border px-3.5 py-2.5 text-sm ${
            message.ton === "succes"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-red-200 bg-red-50 text-red-700"
          }`}
        >
          {message.texte}
        </p>
      ) : null}

      <div className="overflow-x-auto">
        <table className="data-table min-w-[42rem]">
          <thead>
            <tr>
              <th>القسم</th>
              <th className="centre" style={{ width: "7rem" }}>
                عتبة النجاح
              </th>
              <th className="centre" style={{ width: "7rem" }}>
                حد التعويض
              </th>
              <th>سبب القرار</th>
              <th className="fin" style={{ width: "6rem" }}>
                حفظ
              </th>
            </tr>
          </thead>
          <tbody>
            {seuils.map((seuil) => (
              <tr key={seuil.section}>
                <td>
                  <p className="font-medium">{seuil.section_name}</p>
                  <p className="text-[11px] text-gris">
                    {seuil.propre_au_fasl
                      ? `قرار خاص بهذا الفصل (v${seuil.version})`
                      : "العتبة العامة للسنة"}
                    {seuil.note ? ` · ${seuil.note}` : ""}
                  </p>
                </td>
                <td className="centre">
                  <input
                    type="text"
                    inputMode="decimal"
                    className="champ-note"
                    disabled={verrouille}
                    value={barres[seuil.section] ?? seuil.pass_threshold}
                    aria-label={`عتبة النجاح ${seuil.section_name}`}
                    onChange={(event) =>
                      setBarres((precedent) => ({
                        ...precedent,
                        [seuil.section]: event.target.value,
                      }))
                    }
                  />
                </td>
                <td className="centre">
                  <input
                    type="text"
                    inputMode="decimal"
                    className="champ-note"
                    disabled={verrouille}
                    value={planchers[seuil.section] ?? seuil.compensation_floor}
                    aria-label={`حد التعويض ${seuil.section_name}`}
                    onChange={(event) =>
                      setPlanchers((precedent) => ({
                        ...precedent,
                        [seuil.section]: event.target.value,
                      }))
                    }
                  />
                </td>
                <td>
                  <input
                    type="text"
                    className="champ"
                    disabled={verrouille}
                    placeholder="اختياري"
                    aria-label={`سبب قرار ${seuil.section_name}`}
                    value={motifs[seuil.section] ?? ""}
                    onChange={(event) =>
                      setMotifs((precedent) => ({
                        ...precedent,
                        [seuil.section]: event.target.value,
                      }))
                    }
                  />
                </td>
                <td className="fin">
                  <button
                    type="button"
                    onClick={() => enregistrer(seuil)}
                    disabled={verrouille || enCours === seuil.section}
                    className="rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                    style={{
                      background: "linear-gradient(135deg,#006633,#008844)",
                    }}
                  >
                    {enCours === seuil.section ? "…" : "حفظ"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Surcharge d'une decision par le conseil.
 *
 * Le motif est obligatoire cote serveur ; il l'est aussi ici pour que
 * l'utilisateur le sache avant d'envoyer.
 */
export function BoutonSurcharge({
  resultatId,
  decisionActuelle,
  verrouille,
}: {
  resultatId: number;
  decisionActuelle: OverallDecision;
  verrouille: boolean;
}) {
  const router = useRouter();
  const [ouvert, setOuvert] = useState(false);
  const [motif, setMotif] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);

  const cible: OverallDecision =
    decisionActuelle === "PASSED" ? "RESIT" : "PASSED";
  const libelleCible = cible === "PASSED" ? "ناجحة" : "استدراك";

  if (verrouille) {
    return <span className="text-xs text-gris">منشور</span>;
  }

  if (!ouvert) {
    return (
      <button
        type="button"
        onClick={() => setOuvert(true)}
        className="rounded-lg border border-gray-200 px-2.5 py-1 text-xs text-gris transition-colors hover:bg-gray-50 hover:text-dark"
      >
        تعديل القرار
      </button>
    );
  }

  async function valider() {
    if (motif.trim().length < 5) {
      setErreur("السبب مطلوب.");
      return;
    }
    setEnCours(true);
    setErreur(null);
    try {
      await appeler(`semester-results/${resultatId}/override`, {
        decision: cible,
        reason: motif.trim(),
      });
      setOuvert(false);
      setMotif("");
      router.refresh();
    } catch (e) {
      setErreur(e instanceof Error ? e.message : "خطأ غير متوقع.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1.5">
      <input
        type="text"
        value={motif}
        onChange={(event) => setMotif(event.target.value)}
        placeholder={`سبب التحويل إلى «${libelleCible}»`}
        aria-label="سبب تعديل القرار"
        className="w-full min-w-40 rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-dark-soft sm:w-56"
      />
      <div className="flex gap-1.5">
        <button
          type="button"
          onClick={valider}
          disabled={enCours}
          className="rounded-lg px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
          style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
        >
          {enCours ? "…" : `تحويل إلى ${libelleCible}`}
        </button>
        <button
          type="button"
          onClick={() => {
            setOuvert(false);
            setErreur(null);
          }}
          className="rounded-lg border border-gray-200 px-2.5 py-1 text-xs text-gris"
        >
          إلغاء
        </button>
      </div>
      {erreur ? <span className="text-xs text-red-600">{erreur}</span> : null}
    </div>
  );
}
