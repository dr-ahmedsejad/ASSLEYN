"use client";

import { Fragment, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Lock, ShieldCheck, UserCog } from "lucide-react";

import { ReinitialisationMotDePasse } from "@/components/ReinitialisationMotDePasse";
import type {
  DetailDroitsUtilisateur,
  MatriceDroits,
  UtilisateurDroits,
} from "@/lib/types";

import { Alerte, Carte, Nombre, Pastille, Vide } from "./ui";

async function envoyer(chemin: string, methode: "PUT", corps: unknown) {
  const reponse = await fetch(`/api/bff/${chemin}`, {
    method: methode,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  const payload = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    throw new Error(premierMessage(payload) ?? "تعذر حفظ الصلاحيات.");
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

/* ================================================================== */
/* Matrice des droits par role                                        */
/* ================================================================== */

export function MatriceParRole({ matrice }: { matrice: MatriceDroits }) {
  const router = useRouter();
  const [brouillon, setBrouillon] = useState<Map<string, boolean>>(new Map());
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<{
    ton: "succes" | "danger";
    texte: string;
  } | null>(null);

  const cle = (role: string, permission: string) => `${role}|${permission}`;

  function etat(role: string, permission: string, accordee: boolean): boolean {
    return brouillon.get(cle(role, permission)) ?? accordee;
  }

  function basculer(role: string, permission: string, valeur: boolean) {
    setBrouillon((precedent) => {
      const copie = new Map(precedent);
      copie.set(cle(role, permission), valeur);
      return copie;
    });
    setMessage(null);
  }

  async function enregistrer() {
    if (brouillon.size === 0) return;
    setEnCours(true);
    setMessage(null);
    try {
      const resultat = await envoyer("rbac/matrice", "PUT", {
        attributions: [...brouillon.entries()].map(([identifiant, accordee]) => {
          const [role, permission] = identifiant.split("|");
          return { role, permission, accordee };
        }),
      });
      setBrouillon(new Map());
      setMessage({
        ton: "succes",
        texte: `تم منح ${resultat.accordees} صلاحية وسحب ${resultat.retirees}.`,
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
      titre="صلاحيات الأدوار"
      description="ما يراه كل دور في القائمة الجانبية، وما تسمح به الواجهة البرمجية — الشيئان مرتبطان بنفس الصلاحية."
      actions={
        <div className="flex flex-wrap items-center gap-3">
          {brouillon.size > 0 ? (
            <span className="chiffres text-xs font-medium text-yellow-700">
              {brouillon.size} تعديل غير محفوظ
            </span>
          ) : null}
          <button
            type="button"
            onClick={enregistrer}
            disabled={enCours || brouillon.size === 0}
            className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
          >
            <Check size={15} />
            {enCours ? "…" : "حفظ"}
          </button>
        </div>
      }
      sansPadding
    >
      {message ? (
        <div className="px-4 pt-4 sm:px-5">
          <Alerte ton={message.ton}>{message.texte}</Alerte>
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="data-table min-w-[44rem]">
          <thead>
            <tr>
              <th>الصلاحية</th>
              {matrice.roles.map((role) => (
                <th key={role.code} className="centre">
                  {role.libelle}
                  <span className="chiffres block text-[10px] font-normal opacity-70">
                    {role.utilisateurs} مستخدم
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrice.categories.map((categorie) => (
              // La cle appartient a l'element rendu par map — ici le fragment,
              // pas la premiere ligne qu'il contient.
              <Fragment key={categorie.titre}>
                <tr className="bg-gray-50">
                  <td
                    colSpan={matrice.roles.length + 1}
                    className="text-xs font-bold tracking-widest text-gris"
                  >
                    {categorie.titre}
                  </td>
                </tr>
                {categorie.permissions.map((permission) => (
                  <tr key={permission.code}>
                    <td>
                      <p className="font-medium">{permission.libelle}</p>
                      <code className="text-[11px] text-gris" dir="ltr">
                        {permission.code}
                      </code>
                    </td>
                    {matrice.roles.map((role) => {
                      const cellule = permission.roles[role.code];
                      const coche = etat(
                        role.code,
                        permission.code,
                        cellule.accordee,
                      );
                      return (
                        <td key={role.code} className="centre">
                          {cellule.verrouillee ? (
                            <span
                              title="صلاحية لا يمكن سحبها، وإلا تعذّرت إدارة النظام"
                              className="inline-flex items-center gap-1 text-xs text-gris"
                            >
                              <Lock size={13} />
                              <Check size={14} className="text-primary" />
                            </span>
                          ) : (
                            <input
                              type="checkbox"
                              checked={coche}
                              aria-label={`${permission.libelle} — ${role.libelle}`}
                              onChange={(event) =>
                                basculer(
                                  role.code,
                                  permission.code,
                                  event.target.checked,
                                )
                              }
                              className="h-4 w-4 accent-primary"
                            />
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <p className="border-t border-gray-100 px-4 py-3 text-xs leading-relaxed text-gris sm:px-5">
        سحب صلاحية من دور يُخفي مدخل القائمة ويغلق المسار في الواجهة البرمجية
        معا. الصلاحيات المقفلة
        <Lock size={11} className="mx-1 inline" />
        لا تُسحب حتى لا يبقى النظام بلا إدارة.
      </p>
    </Carte>
  );
}

/* ================================================================== */
/* Droits individuels                                                 */
/* ================================================================== */

export function DroitsIndividuels({
  utilisateurs,
  detail,
}: {
  utilisateurs: UtilisateurDroits[];
  detail: DetailDroitsUtilisateur | null;
}) {
  const router = useRouter();
  const [brouillon, setBrouillon] = useState<Map<string, boolean | null>>(
    new Map(),
  );
  const [motif, setMotif] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [message, setMessage] = useState<{
    ton: "succes" | "danger";
    texte: string;
  } | null>(null);

  function choix(code: string, actuel: boolean | null): boolean | null {
    return brouillon.has(code) ? (brouillon.get(code) ?? null) : actuel;
  }

  function definir(code: string, valeur: boolean | null) {
    setBrouillon((precedent) => new Map(precedent).set(code, valeur));
    setMessage(null);
  }

  async function enregistrer() {
    if (!detail || brouillon.size === 0) return;
    setEnCours(true);
    setMessage(null);
    try {
      const resultat = await envoyer(`rbac/utilisateurs/${detail.id}`, "PUT", {
        exceptions: [...brouillon.entries()].map(([permission, granted]) => ({
          permission,
          granted,
          reason: motif.trim(),
        })),
      });
      setBrouillon(new Map());
      setMotif("");
      setMessage({
        ton: "succes",
        texte: `تم تسجيل ${resultat.posees} استثناء ورفع ${resultat.levees}.`,
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
      titre="صلاحيات فردية"
      description="لإسناد قدرة إلى شخص بعينه دون تغيير دوره — مثل إدخال النقاط."
      sansPadding
    >
      <div className="grid gap-0 lg:grid-cols-[16rem_1fr]">
        {/* Liste des personnes */}
        <div className="border-b border-gray-100 lg:border-b-0 lg:border-e">
          <ul className="max-h-96 divide-y divide-gray-100 overflow-y-auto">
            {utilisateurs.length === 0 ? (
              <li>
                <Vide>لا يوجد مستخدمون.</Vide>
              </li>
            ) : (
              utilisateurs.map((personne) => {
                const actif = personne.id === detail?.id;
                return (
                  <li key={personne.id}>
                    <a
                      href={`/droits?utilisateur=${personne.id}`}
                      className={`flex items-center justify-between gap-2 px-4 py-3 transition-colors ${
                        actif
                          ? "bg-green-50 text-primary"
                          : "text-dark-soft hover:bg-gray-50"
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">
                          {personne.full_name_ar}
                        </span>
                        <span className="block text-[11px] text-gris">
                          {personne.role_display}
                          <span className="chiffres mx-1">
                            · {personne.username}
                          </span>
                        </span>
                      </span>
                      {personne.exceptions.length > 0 ? (
                        <Pastille
                          libelle={String(personne.exceptions.length)}
                          variante="warning"
                        />
                      ) : null}
                    </a>
                  </li>
                );
              })
            )}
          </ul>
        </div>

        {/* Detail de la personne choisie */}
        <div className="p-4 sm:p-5">
          {!detail ? (
            <Vide>اختر شخصا من القائمة.</Vide>
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="flex items-center gap-2 font-semibold text-dark">
                    <UserCog size={16} className="text-gris" />
                    {detail.full_name_ar}
                  </p>
                  <p className="text-xs text-gris">
                    {detail.role_display}
                    <span className="chiffres mx-1">· {detail.username}</span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={enregistrer}
                  disabled={enCours || brouillon.size === 0}
                  className="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                  style={{
                    background: "linear-gradient(135deg,#006633,#008844)",
                  }}
                >
                  <ShieldCheck size={15} />
                  {enCours ? "…" : "حفظ"}
                </button>
              </div>

              {message ? (
                <div className="mb-4">
                  <Alerte ton={message.ton}>{message.texte}</Alerte>
                </div>
              ) : null}

              {/* L'administration rend un acces sans connaitre l'ancien mot de
                  passe : c'est le seul cas ou elle est appelee. Pour une
                  etudiante, le champ propose d'emblee la regle de
                  l'etablissement — son numero ecrit deux fois. */}
              <div className="mb-4">
                <ReinitialisationMotDePasse
                  key={detail.id}
                  utilisateur={detail.id}
                  nom={detail.full_name_ar}
                  suggestion={
                    detail.role === "STUDENT"
                      ? `${detail.username}${detail.username}`
                      : undefined
                  }
                />
              </div>

              <div className="overflow-x-auto">
                <table className="data-table min-w-[30rem]">
                  <thead>
                    <tr>
                      <th>الصلاحية</th>
                      <th className="centre">حسب الدور</th>
                      <th className="centre" style={{ width: "14rem" }}>
                        القرار
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.permissions.map((permission) => {
                      const valeur = choix(permission.code, permission.exception);
                      return (
                        <tr key={permission.code}>
                          <td>
                            <p className="font-medium">{permission.libelle}</p>
                            <code className="text-[11px] text-gris" dir="ltr">
                              {permission.code}
                            </code>
                          </td>
                          <td className="centre text-xs text-gris">
                            {permission.par_le_role ? "ممنوحة" : "—"}
                          </td>
                          <td className="centre">
                            <div className="flex justify-center gap-1">
                              {(
                                [
                                  { v: null, t: "حسب الدور" },
                                  { v: true, t: "منح" },
                                  { v: false, t: "منع" },
                                ] as const
                              ).map((option) => {
                                const actif = valeur === option.v;
                                return (
                                  <button
                                    key={String(option.v)}
                                    type="button"
                                    onClick={() =>
                                      definir(permission.code, option.v)
                                    }
                                    className={`rounded-lg border px-2 py-1 text-[11px] font-medium transition-colors ${
                                      actif
                                        ? option.v === false
                                          ? "border-red-200 bg-red-50 text-red-700"
                                          : option.v === true
                                            ? "border-primary bg-green-50 text-primary"
                                            : "border-gray-300 bg-gray-100 text-dark-soft"
                                        : "border-gray-200 text-gris hover:bg-gray-50"
                                    }`}
                                  >
                                    {option.t}
                                  </button>
                                );
                              })}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <label className="mt-4 block">
                <span className="mb-1.5 block text-xs font-medium text-gris">
                  سبب القرار (اختياري)
                </span>
                <input
                  type="text"
                  value={motif}
                  onChange={(event) => setMotif(event.target.value)}
                  placeholder="مثلا: تكليف مؤقت بإدخال نقاط قسم"
                  className="champ"
                />
              </label>

              <p className="mt-3 text-xs leading-relaxed text-gris">
                الاستثناء الفردي يعلو على الدور. «منح» يضيف قدرة لا يمنحها
                الدور، و«منع» يسحب قدرة يمنحها. الأستاذ يبقى محصورا في المواد
                المسندة إليه: منحه إدخال النقاط لا يفتح له مواد غيره.
              </p>
            </>
          )}
        </div>
      </div>

      <p className="border-t border-gray-100 px-4 py-3 text-xs text-gris sm:px-5">
        عدد الاستثناءات الحالية:{" "}
        <Nombre>
          {utilisateurs.reduce((total, u) => total + u.exceptions.length, 0)}
        </Nombre>
      </p>
    </Carte>
  );
}
