"use client";

import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import { LogIn, TriangleAlert } from "lucide-react";

import { ChampMotDePasse } from "@/components/ChampMotDePasse";
import { CompteARebours } from "@/components/CompteARebours";
import { connexion, type FormState } from "@/lib/auth";

const ETAT_INITIAL: FormState = {};

function BoutonEnvoyer({ bloque }: { bloque: boolean }) {
  const { pending } = useFormStatus();
  const inactif = pending || bloque;
  return (
    <button
      type="submit"
      disabled={inactif}
      className="flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: "linear-gradient(135deg, #004d24, #006633)" }}
    >
      <LogIn size={16} />
      {pending ? "جارٍ التحقق…" : "دخول"}
    </button>
  );
}

export function FormulaireConnexion() {
  const [etat, action] = useActionState(connexion, ETAT_INITIAL);
  // Le minuteur est arrive a zero : le bouton redevient utilisable sans
  // recharger la page.
  const [delaiEcoule, setDelaiEcoule] = useState(false);

  const secondes = etat.secondesRestantes ?? 0;
  const bloque = secondes > 0 && !delaiEcoule;

  return (
    <form action={action} className="space-y-4">
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
          required
          autoComplete="username"
          autoFocus
          className="champ"
        />
      </div>

      <ChampMotDePasse
        nom="password"
        libelle="كلمة السر"
        autoComplete="current-password"
      />

      {secondes > 0 ? (
        <CompteARebours
          key={secondes}
          secondes={secondes}
          niveau={etat.niveau}
          onFin={() => setDelaiEcoule(true)}
        />
      ) : etat.error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700"
        >
          <p>{etat.error}</p>
          {/* Prevenir avant la fermeture vaut mieux que l'expliquer apres :
              l'etudiante corrige tant qu'elle le peut encore. */}
          {etat.tentativesRestantes !== undefined &&
          etat.tentativesRestantes <= 2 ? (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs font-medium">
              <TriangleAlert size={13} />
              <span className="chiffres">
                تبقى {etat.tentativesRestantes} محاولة قبل إقفال الحساب.
              </span>
            </p>
          ) : null}
        </div>
      ) : null}

      <BoutonEnvoyer bloque={bloque} />
    </form>
  );
}
