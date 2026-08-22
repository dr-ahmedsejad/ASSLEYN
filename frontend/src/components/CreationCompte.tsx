"use client";

import { useActionState, useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { Check, Copy, GraduationCap, UserPlus, Users } from "lucide-react";

import { ChampMotDePasse } from "@/components/ChampMotDePasse";
import { creerCompte, type ResultatCreation } from "@/lib/comptes-actions";
import { AIDE_MOT_DE_PASSE } from "@/lib/politique-mot-de-passe";
import { Alerte, Carte } from "./ui";

const ETAT_INITIAL: ResultatCreation = {};

const ROLES = [
  { valeur: "ASSISTANT", libelle: "مساعد الإدارة" },
  { valeur: "TEACHER", libelle: "أستاذ" },
  { valeur: "ADMIN", libelle: "مدير" },
] as const;

function Bouton({ libelle }: { libelle: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
    >
      <UserPlus size={15} />
      {pending ? "جارٍ الإنشاء…" : libelle}
    </button>
  );
}

/**
 * Ouverture d'un compte.
 *
 * Deux formulaires, parce que ce sont deux gestes differents.
 *
 * Pour une etudiante, tout existe deja dans son dossier : il suffit de son
 * numero. Retaper son nom, c'est risquer une seconde orthographe pour une
 * meme personne.
 *
 * Pour le personnel, le **nom complet est saisi**. Il n'est jamais deduit de
 * l'identifiant : `sejad` est une chaine technique, et la translitterer en
 * arabe produit une orthographe que l'interesse ne reconnait pas comme la
 * sienne.
 */
export function CreationCompte() {
  const [etat, action] = useActionState(creerCompte, ETAT_INITIAL);
  const [onglet, setOnglet] = useState<"etudiante" | "personnel">("personnel");
  const [copie, setCopie] = useState(false);

  useEffect(() => {
    if (!copie) return;
    const minuterie = setTimeout(() => setCopie(false), 2000);
    return () => clearTimeout(minuterie);
  }, [copie]);

  return (
    <Carte titre="فتح حساب جديد">
      {/* Le mot de passe n'apparait qu'ici, une seule fois : il n'est stocke
          nulle part en clair. */}
      {etat.motDePasse ? (
        <div className="mb-4 rounded-xl border border-green-200 bg-green-50 px-3.5 py-3">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-green-800">
            <Check size={15} />
            تم فتح حساب {etat.nom} — {etat.role}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <code
              dir="ltr"
              className="rounded-lg border border-green-300 bg-white px-3 py-2 text-sm font-bold text-dark"
            >
              {etat.username}
            </code>
            <code
              dir="ltr"
              className="flex-1 rounded-lg border border-green-300 bg-white px-3 py-2 text-center text-lg font-bold tracking-wider text-dark"
            >
              {etat.motDePasse}
            </code>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard?.writeText(
                  `${etat.username} / ${etat.motDePasse}`,
                );
                setCopie(true);
              }}
              aria-label="نسخ"
              title="نسخ"
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-green-300 bg-white text-green-700 transition-colors hover:bg-green-100"
            >
              {copie ? <Check size={16} /> : <Copy size={16} />}
            </button>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-green-800">
            كلمة السر تظهر مرة واحدة فقط، وسيُطلب تغييرها عند أول دخول.
          </p>
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap gap-2">
        {(
          [
            { cle: "personnel", libelle: "موظف", icone: Users },
            { cle: "etudiante", libelle: "طالبة", icone: GraduationCap },
          ] as const
        ).map((choix) => {
          const actif = onglet === choix.cle;
          const Icone = choix.icone;
          return (
            <button
              key={choix.cle}
              type="button"
              onClick={() => setOnglet(choix.cle)}
              aria-pressed={actif}
              className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-sm transition-colors ${
                actif
                  ? "border-transparent text-white"
                  : "border-gray-200 bg-white text-gris hover:bg-gray-50"
              }`}
              style={
                actif
                  ? { background: "linear-gradient(135deg,#004d24,#006633)" }
                  : undefined
              }
            >
              <Icone size={14} />
              {choix.libelle}
            </button>
          );
        })}
      </div>

      {onglet === "etudiante" ? (
        <form key="etudiante" action={action} className="space-y-3">
          <div className="max-w-xs">
            <label
              htmlFor="matricule"
              className="mb-1.5 block text-sm font-medium text-dark-soft"
            >
              رقم الطالبة
            </label>
            <input
              id="matricule"
              name="matricule"
              type="text"
              inputMode="numeric"
              dir="ltr"
              required
              placeholder="24060"
              className="champ"
            />
          </div>

          <Alerte ton="info">
            الاسم يُؤخذ من ملف الطالبة كما هو، واسم المستخدم هو رقمها، وكلمة
            السر الأولى هي رقمها مكتوبا مرتين.
          </Alerte>

          {etat.erreur ? (
            <p role="alert" className="text-sm text-red-700">
              {etat.erreur}
            </p>
          ) : null}

          <Bouton libelle="فتح الحساب" />
        </form>
      ) : (
        <form key="personnel" action={action} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label
                htmlFor="full_name_ar"
                className="mb-1.5 block text-sm font-medium text-dark-soft"
              >
                الاسم الكامل
              </label>
              <input
                id="full_name_ar"
                name="full_name_ar"
                type="text"
                required
                placeholder="خديجة بنت أحمد"
                className="champ"
              />
            </div>

            <div>
              <label
                htmlFor="username"
                className="mb-1.5 block text-sm font-medium text-dark-soft"
              >
                اسم المستخدم
              </label>
              <input
                id="username"
                name="username"
                type="text"
                dir="ltr"
                required
                autoComplete="off"
                placeholder="khadija"
                className="champ"
              />
            </div>

            <ChampMotDePasse
              nom="password"
              libelle="كلمة السر"
              autoComplete="new-password"
            />

            <div>
              <label
                htmlFor="role"
                className="mb-1.5 block text-sm font-medium text-dark-soft"
              >
                الدور
              </label>
              <select id="role" name="role" required className="champ">
                {ROLES.map((r) => (
                  <option key={r.valeur} value={r.valeur}>
                    {r.libelle}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="phone"
                className="mb-1.5 block text-sm font-medium text-dark-soft"
              >
                الهاتف <span className="text-gris">(اختياري)</span>
              </label>
              <input
                id="phone"
                name="phone"
                type="tel"
                dir="ltr"
                className="champ"
              />
            </div>
          </div>

          <p className="text-xs leading-relaxed text-gris">
            {AIDE_MOT_DE_PASSE} سيُطلب من صاحب الحساب تغييرها عند أول دخول.
          </p>

          {etat.erreur ? (
            <p role="alert" className="text-sm text-red-700">
              {etat.erreur}
            </p>
          ) : null}

          <Bouton libelle="فتح الحساب" />
        </form>
      )}
    </Carte>
  );
}
