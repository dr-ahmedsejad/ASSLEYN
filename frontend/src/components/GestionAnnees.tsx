"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarPlus, UserPlus } from "lucide-react";

import type { AcademicYear, Enrollment, Section } from "@/lib/types";

import { Alerte, Carte, Nombre } from "./ui";

async function poster(chemin: string, corps: unknown) {
  const reponse = await fetch(`/api/bff/${chemin}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  const payload = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    throw new Error(premierMessage(payload) ?? "تعذر تنفيذ العملية.");
  }
  return payload;
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
 * Ouverture de l'annee suivante.
 *
 * On recopie la structure — فصول, programmes, coefficients, reglement — mais
 * jamais les notes ni les inscriptions. La reinscription des etudiantes est un
 * acte distinct, ci-dessous.
 */
export function OuvrirAnneeSuivante({ source }: { source: AcademicYear }) {
  const router = useRouter();

  const anneeSuivante = suggererLibelle(source.label);
  const [label, setLabel] = useState(anneeSuivante.label);
  const [debut, setDebut] = useState(decalerUnAn(source.start_date));
  const [fin, setFin] = useState(decalerUnAn(source.end_date));
  const [activer, setActiver] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<{
    ton: "succes" | "danger";
    texte: string;
  } | null>(null);

  async function valider() {
    setEnCours(true);
    setMessage(null);
    try {
      const resultat = await poster(`years/${source.id}/dupliquer`, {
        label,
        start_date: debut,
        end_date: fin,
        activer,
      });
      setMessage({
        ton: "succes",
        texte:
          `تم فتح السنة ${resultat.label}: ${resultat.fusul_crees} فصول` +
          ` و ${resultat.programmes_copies} مادة منقولة.`,
      });
      router.refresh();
    } catch (erreur) {
      setMessage({
        ton: "danger",
        texte: erreur instanceof Error ? erreur.message : "خطأ غير متوقع.",
      });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <Carte
      titre="فتح السنة الموالية"
      description={`نسخ بنية ${source.label}: الفصول والمواد والضوارب. النقاط والتسجيلات لا تُنقل.`}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Champ libelle="السنة الدراسية">
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="champ"
            />
        </Champ>
        <Champ libelle="تاريخ البداية">
          <input
            type="date"
            value={debut}
            onChange={(e) => setDebut(e.target.value)}
            className="champ"
            />
        </Champ>
        <Champ libelle="تاريخ النهاية">
          <input
            type="date"
            value={fin}
            onChange={(e) => setFin(e.target.value)}
            className="champ"
            />
        </Champ>
        <Champ libelle="التفعيل">
          <label className="flex h-[42px] items-center gap-2 rounded-xl border border-gray-200 px-3 text-sm text-dark-soft">
            <input
              type="checkbox"
              checked={activer}
              onChange={(e) => setActiver(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            اجعلها السنة الجارية
          </label>
        </Champ>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={valider}
          disabled={enCours}
          className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
        >
          <CalendarPlus size={16} />
          {enCours ? "…" : "فتح السنة"}
        </button>
      </div>

      {message ? (
        <div className="mt-3">
          <Alerte ton={message.ton}>{message.texte}</Alerte>
        </div>
      ) : null}
    </Carte>
  );
}

/**
 * Reinscription en lot dans l'annee suivante.
 *
 * La section de destination est choisie par l'administration : le systeme ne
 * suppose aucun parcours automatique entre les اقسام.
 */
export function Reinscription({
  inscriptions,
  annees,
  sections,
  anneeCourante,
}: {
  inscriptions: Enrollment[];
  annees: AcademicYear[];
  sections: Section[];
  anneeCourante: number | null;
}) {
  const router = useRouter();
  const [selection, setSelection] = useState<Set<number>>(new Set());
  const [anneeCible, setAnneeCible] = useState(
    String(annees.find((a) => a.id !== anneeCourante)?.id ?? ""),
  );
  const [sectionCible, setSectionCible] = useState(
    String(sections[0]?.id ?? ""),
  );
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<{
    ton: "succes" | "danger";
    texte: string;
  } | null>(null);

  const toutesCochees =
    inscriptions.length > 0 && selection.size === inscriptions.length;

  function basculer(studentId: number) {
    setSelection((precedent) => {
      const copie = new Set(precedent);
      if (copie.has(studentId)) copie.delete(studentId);
      else copie.add(studentId);
      return copie;
    });
  }

  function toutBasculer() {
    setSelection(
      toutesCochees ? new Set() : new Set(inscriptions.map((i) => i.student)),
    );
  }

  async function valider() {
    if (selection.size === 0) {
      setMessage({ ton: "danger", texte: "اختر طالبة واحدة على الأقل." });
      return;
    }
    if (!anneeCible || !sectionCible) {
      setMessage({ ton: "danger", texte: "حدد السنة والقسم." });
      return;
    }

    setEnCours(true);
    setMessage(null);
    try {
      const resultat = await poster("enrollments/reinscrire", {
        year: Number(anneeCible),
        section: Number(sectionCible),
        students: [...selection],
      });
      const deja = resultat.deja_inscrites?.length ?? 0;
      setMessage({
        ton: "succes",
        texte:
          `تم تسجيل ${resultat.inscrites} طالبة في ${resultat.section}` +
          ` (${resultat.annee})` +
          (deja > 0 ? ` — ${deja} مسجلة أصلا.` : "."),
      });
      setSelection(new Set());
      router.refresh();
    } catch (erreur) {
      setMessage({
        ton: "danger",
        texte: erreur instanceof Error ? erreur.message : "خطأ غير متوقع.",
      });
    } finally {
      setEnCours(false);
    }
  }

  return (
    <Carte
      titre="تسجيل الطالبات في السنة الموالية"
      description="اختر الطالبات ثم القسم الذي تنتقلن إليه."
      sansPadding
    >
      <div className="grid gap-3 border-b border-gray-100 px-4 py-4 sm:grid-cols-2 sm:px-5">
        <Champ libelle="السنة الموالية">
          <select
            value={anneeCible}
            onChange={(e) => setAnneeCible(e.target.value)}
            className="champ"
          >
            <option value="">— اختر السنة —</option>
            {annees.map((annee) => (
              <option key={annee.id} value={annee.id}>
                {annee.label}
              </option>
            ))}
          </select>
        </Champ>
        <Champ libelle="القسم الجديد">
          <select
            value={sectionCible}
            onChange={(e) => setSectionCible(e.target.value)}
            className="champ"
          >
            {sections.map((section) => (
              <option key={section.id} value={section.id}>
                {section.name_ar}
              </option>
            ))}
          </select>
        </Champ>
      </div>

      {inscriptions.length === 0 ? (
        <p className="py-10 text-center text-sm text-gris">
          لا توجد طالبات في هذا الاختيار.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table min-w-[30rem]">
            <thead>
              <tr>
                <th style={{ width: "3rem" }}>
                  <input
                    type="checkbox"
                    checked={toutesCochees}
                    onChange={toutBasculer}
                    aria-label="اختيار الكل"
                    className="h-4 w-4 accent-primary"
                  />
                </th>
                <th>رقم الطالبة</th>
                <th>الاسم الكامل</th>
                <th className="fin">القسم الحالي</th>
              </tr>
            </thead>
            <tbody>
              {inscriptions.map((inscription) => (
                <tr key={inscription.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selection.has(inscription.student)}
                      onChange={() => basculer(inscription.student)}
                      aria-label={`اختيار ${inscription.full_name_ar}`}
                      className="h-4 w-4 accent-primary"
                    />
                  </td>
                  <td>
                    <Nombre>{inscription.matricule}</Nombre>
                  </td>
                  <td className="font-medium">{inscription.full_name_ar}</td>
                  <td className="fin text-gris">{inscription.section_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-gray-100 px-4 py-4 sm:px-5">
        <button
          type="button"
          onClick={valider}
          disabled={enCours || selection.size === 0}
          className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
        >
          <UserPlus size={16} />
          {enCours ? "…" : "تسجيل المحددات"}
        </button>
        <span className="chiffres text-sm text-gris">
          {selection.size} / {inscriptions.length} محددة
        </span>
      </div>

      {message ? (
        <div className="px-4 pb-4 sm:px-5">
          <Alerte ton={message.ton}>{message.texte}</Alerte>
        </div>
      ) : null}
    </Carte>
  );
}

function Champ({
  libelle,
  children,
}: {
  libelle: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-gris">
        {libelle}
      </span>
      {children}
    </label>
  );
}

/** « 2025-2026 » → « 2026-2027 ». */
function suggererLibelle(label: string): { label: string } {
  const correspondance = label.match(/^(\d{4})\D+(\d{4})$/);
  if (!correspondance) return { label: "" };
  return {
    label: `${Number(correspondance[1]) + 1}-${Number(correspondance[2]) + 1}`,
  };
}

function decalerUnAn(date: string): string {
  const correspondance = date.match(/^(\d{4})(-\d{2}-\d{2})$/);
  return correspondance
    ? `${Number(correspondance[1]) + 1}${correspondance[2]}`
    : date;
}
