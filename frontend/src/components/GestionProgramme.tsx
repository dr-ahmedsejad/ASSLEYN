"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Plus, Power, Trash2 } from "lucide-react";

import type { Curriculum, Section, Semester, Subject } from "@/lib/types";

import { Alerte, Carte, Nombre, Vide } from "./ui";

/**
 * Gestion du programme d'un فصل : quelles matieres, avec quel coefficient.
 *
 * Modifier un coefficient change les moyennes de toute la section. Chaque
 * enregistrement declenche donc un recalcul cote serveur, et l'ecran le dit.
 * L'API refuse d'elle-meme toute modification apres publication du فصل, et
 * refuse de supprimer une matiere qui porte deja des notes — on se contente
 * ici d'afficher son message.
 */

async function appeler(
  chemin: string,
  methode: "POST" | "PATCH" | "DELETE",
  corps?: unknown,
): Promise<unknown> {
  const reponse = await fetch(`/api/bff/${chemin}`, {
    method: methode,
    headers: corps ? { "Content-Type": "application/json" } : undefined,
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

export function GestionProgramme({
  section,
  fasl,
  programme,
  matieres,
  verrouille,
}: {
  section: Section;
  fasl: Semester;
  programme: Curriculum[];
  matieres: Subject[];
  verrouille: boolean;
}) {
  const router = useRouter();
  const [message, setMessage] = useState<{
    ton: "succes" | "danger";
    texte: string;
  } | null>(null);
  const [enCours, setEnCours] = useState<string | null>(null);

  // Coefficients en cours d'edition, indexes par identifiant de programme.
  const [saisies, setSaisies] = useState<Record<number, string>>({});

  const [nouvelleMatiere, setNouvelleMatiere] = useState("");
  const [nouveauCoefficient, setNouveauCoefficient] = useState("");

  const dejaAuProgramme = new Set(programme.map((p) => p.subject));
  const disponibles = matieres.filter(
    (m) => m.is_active && !dejaAuProgramme.has(m.id),
  );

  const totalCoefficients = programme
    .filter((p) => p.is_active)
    .reduce((somme, p) => somme + Number(p.coefficient), 0);

  async function executer(cle: string, action: () => Promise<unknown>) {
    setEnCours(cle);
    setMessage(null);
    try {
      await action();
      router.refresh();
      return true;
    } catch (erreur) {
      setMessage({
        ton: "danger",
        texte: erreur instanceof Error ? erreur.message : "خطأ غير متوقع.",
      });
      return false;
    } finally {
      setEnCours(null);
    }
  }

  async function enregistrerCoefficient(ligne: Curriculum) {
    const brut = (saisies[ligne.id] ?? ligne.coefficient).replace(",", ".");
    const valeur = Number(brut);
    if (Number.isNaN(valeur) || valeur <= 0) {
      setMessage({ ton: "danger", texte: "الضارب يجب أن يكون رقما أكبر من صفر." });
      return;
    }
    const ok = await executer(`coef-${ligne.id}`, () =>
      appeler(`curricula/${ligne.id}`, "PATCH", { coefficient: brut }),
    );
    if (ok) {
      setSaisies((precedent) => {
        const copie = { ...precedent };
        delete copie[ligne.id];
        return copie;
      });
      setMessage({
        ton: "succes",
        texte: `تم تحديث ضارب ${ligne.subject_name}. أعيد احتساب معدلات القسم.`,
      });
    }
  }

  async function basculerActivite(ligne: Curriculum) {
    const ok = await executer(`actif-${ligne.id}`, () =>
      appeler(`curricula/${ligne.id}`, "PATCH", { is_active: !ligne.is_active }),
    );
    if (ok) {
      setMessage({
        ton: "succes",
        texte: ligne.is_active
          ? `تم تعطيل ${ligne.subject_name}.`
          : `تم تفعيل ${ligne.subject_name}.`,
      });
    }
  }

  async function supprimer(ligne: Curriculum) {
    const ok = await executer(`suppr-${ligne.id}`, () =>
      appeler(`curricula/${ligne.id}`, "DELETE"),
    );
    if (ok) {
      setMessage({
        ton: "succes",
        texte: `تم حذف ${ligne.subject_name} من البرنامج.`,
      });
    }
  }

  async function ajouter() {
    if (!nouvelleMatiere) {
      setMessage({ ton: "danger", texte: "اختر المادة أولا." });
      return;
    }
    const brut = nouveauCoefficient.replace(",", ".");
    const valeur = Number(brut);
    if (!brut || Number.isNaN(valeur) || valeur <= 0) {
      setMessage({ ton: "danger", texte: "الضارب يجب أن يكون رقما أكبر من صفر." });
      return;
    }
    const ok = await executer("ajout", () =>
      appeler("curricula", "POST", {
        section: section.id,
        semester: fasl.id,
        subject: Number(nouvelleMatiere),
        coefficient: brut,
        display_order: programme.length,
      }),
    );
    if (ok) {
      setNouvelleMatiere("");
      setNouveauCoefficient("");
      setMessage({ ton: "succes", texte: "تمت إضافة المادة إلى البرنامج." });
    }
  }

  return (
    <Carte
      titre={`برنامج ${section.name_ar} — الفصل ${fasl.number}`}
      description={`مجموع الضوارب الحالي: ${totalCoefficients}`}
      sansPadding
    >
      <div className="space-y-3 px-4 py-4 sm:px-5">
        {verrouille ? (
          <Alerte ton="warning">
            نتائج هذا الفصل منشورة. لتعديل البرنامج أعد الفصل إلى حالة «مغلق»
            من صفحة المداولة.
          </Alerte>
        ) : (
          <Alerte ton="info">
            تعديل الضارب يغيّر معدلات القسم بأكمله؛ يُعاد الاحتساب تلقائيا عند
            الحفظ.
          </Alerte>
        )}
        {message ? <Alerte ton={message.ton}>{message.texte}</Alerte> : null}
      </div>

      <div className="overflow-x-auto border-t border-gray-100">
        <table className="data-table min-w-[34rem]">
          <thead>
            <tr>
              <th>المادة</th>
              <th className="centre" style={{ width: "9rem" }}>
                الضارب
              </th>
              <th className="centre" style={{ width: "7rem" }}>
                الحالة
              </th>
              <th className="fin" style={{ width: "11rem" }}>
                إجراءات
              </th>
            </tr>
          </thead>
          <tbody>
            {programme.length === 0 ? (
              <tr>
                <td colSpan={4}>
                  <Vide>لم يحدد البرنامج بعد.</Vide>
                </td>
              </tr>
            ) : (
              programme.map((ligne) => {
                const saisie = saisies[ligne.id] ?? ligne.coefficient;
                const modifie = saisie !== ligne.coefficient;
                return (
                  <tr key={ligne.id} className={ligne.is_active ? "" : "opacity-50"}>
                    <td className="font-medium">{ligne.subject_name}</td>
                    <td className="centre">
                      <input
                        type="text"
                        inputMode="decimal"
                        className="champ-note"
                        value={saisie}
                        disabled={verrouille}
                        aria-label={`ضارب ${ligne.subject_name}`}
                        onChange={(event) =>
                          setSaisies((precedent) => ({
                            ...precedent,
                            [ligne.id]: event.target.value,
                          }))
                        }
                      />
                    </td>
                    <td className="centre text-xs text-gris">
                      {ligne.is_active ? "نشطة" : "معطلة"}
                    </td>
                    <td className="fin">
                      <div className="flex items-center justify-end gap-1.5">
                        <BoutonAction
                          titre="حفظ الضارب"
                          actif={modifie && !verrouille}
                          charge={enCours === `coef-${ligne.id}`}
                          principal
                          onClick={() => enregistrerCoefficient(ligne)}
                        >
                          <Check size={14} />
                        </BoutonAction>
                        <BoutonAction
                          titre={ligne.is_active ? "تعطيل" : "تفعيل"}
                          actif={!verrouille}
                          charge={enCours === `actif-${ligne.id}`}
                          onClick={() => basculerActivite(ligne)}
                        >
                          <Power size={14} />
                        </BoutonAction>
                        <BoutonAction
                          titre="حذف من البرنامج"
                          actif={!verrouille}
                          charge={enCours === `suppr-${ligne.id}`}
                          danger
                          onClick={() => supprimer(ligne)}
                        >
                          <Trash2 size={14} />
                        </BoutonAction>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Ajout d'une matiere au programme */}
      <div className="border-t border-gray-100 px-4 py-4 sm:px-5">
        <h3 className="mb-3 text-sm font-semibold text-dark">
          إضافة مادة إلى البرنامج
        </h3>
        {disponibles.length === 0 ? (
          <p className="text-sm text-gris">
            كل المواد المتاحة مدرجة في هذا البرنامج. أضف مادة جديدة إلى
            الكتالوج أولا.
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={nouvelleMatiere}
              disabled={verrouille}
              aria-label="المادة"
              onChange={(event) => setNouvelleMatiere(event.target.value)}
              className="champ max-w-56"
            >
              <option value="">— اختر المادة —</option>
              {disponibles.map((matiere) => (
                <option key={matiere.id} value={matiere.id}>
                  {matiere.name_ar}
                </option>
              ))}
            </select>
            <input
              type="text"
              inputMode="decimal"
              value={nouveauCoefficient}
              disabled={verrouille}
              placeholder="الضارب"
              aria-label="الضارب"
              onChange={(event) => setNouveauCoefficient(event.target.value)}
              className="champ max-w-24 text-center"
                />
            <button
              type="button"
              onClick={ajouter}
              disabled={verrouille || enCours === "ajout"}
              className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
            >
              <Plus size={15} />
              {enCours === "ajout" ? "…" : "إضافة"}
            </button>
          </div>
        )}
      </div>
    </Carte>
  );
}

function BoutonAction({
  titre,
  actif,
  charge,
  principal,
  danger,
  onClick,
  children,
}: {
  titre: string;
  actif: boolean;
  charge: boolean;
  principal?: boolean;
  danger?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const style = principal
    ? "border-primary text-primary hover:bg-green-50"
    : danger
      ? "border-gray-200 text-gris hover:border-red-200 hover:bg-red-50 hover:text-red-600"
      : "border-gray-200 text-gris hover:bg-gray-50 hover:text-dark";

  return (
    <button
      type="button"
      title={titre}
      aria-label={titre}
      onClick={onClick}
      disabled={!actif || charge}
      className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${style}`}
    >
      {charge ? <span className="text-xs">…</span> : children}
    </button>
  );
}

/* ------------------------------------------------------------------ */

/** Catalogue global des matieres, partage par toutes les sections. */
export function CatalogueMatieres({ matieres }: { matieres: Subject[] }) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [nom, setNom] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<{
    ton: "succes" | "danger";
    texte: string;
  } | null>(null);

  async function ajouter() {
    const codeNettoye = code.trim().toUpperCase().replace(/\s+/g, "-");
    if (!codeNettoye || !nom.trim()) {
      setMessage({ ton: "danger", texte: "الرمز واسم المادة مطلوبان." });
      return;
    }
    setEnCours(true);
    setMessage(null);
    try {
      await appeler("subjects", "POST", {
        code: codeNettoye,
        name_ar: nom.trim(),
        display_order: matieres.length,
      });
      setCode("");
      setNom("");
      setMessage({ ton: "succes", texte: "تمت إضافة المادة إلى الكتالوج." });
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
      titre="كتالوج المواد"
      description="المواد المتاحة لكل الأقسام. الضارب لا يُحدد هنا بل في برنامج كل فصل."
      sansPadding
    >
      <div className="overflow-x-auto">
        <table className="data-table min-w-[24rem]">
          <thead>
            <tr>
              <th>المادة</th>
              <th>الرمز</th>
              <th className="fin">الحالة</th>
            </tr>
          </thead>
          <tbody>
            {matieres.map((matiere) => (
              <tr key={matiere.id}>
                <td className="font-medium">{matiere.name_ar}</td>
                <td>
                  <span className="chiffres text-xs text-gris">
                    {matiere.code}
                  </span>
                </td>
                <td className="fin text-xs text-gris">
                  {matiere.is_active ? "نشطة" : "معطلة"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-gray-100 px-4 py-4 sm:px-5">
        <h3 className="mb-3 text-sm font-semibold text-dark">مادة جديدة</h3>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={nom}
            onChange={(event) => setNom(event.target.value)}
            placeholder="اسم المادة"
            aria-label="اسم المادة"
            className="champ max-w-56"
          />
          <input
            type="text"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="CODE"
            aria-label="رمز المادة"
              className="champ max-w-32"
          />
          <button
            type="button"
            onClick={ajouter}
            disabled={enCours}
            className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
          >
            <Plus size={15} />
            {enCours ? "…" : "إضافة"}
          </button>
        </div>
        <p className="mt-2 text-xs text-gris">
          الرمز معرّف تقني ثابت بالأحرف اللاتينية، مثل <Nombre>QURAN</Nombre>.
        </p>
        {message ? (
          <div className="mt-3">
            <Alerte ton={message.ton}>{message.texte}</Alerte>
          </div>
        ) : null}
      </div>
    </Carte>
  );
}
