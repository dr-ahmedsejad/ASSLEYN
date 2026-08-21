"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { LogIn } from "lucide-react";

import { ChampMotDePasse } from "@/components/ChampMotDePasse";
import { connexion, type FormState } from "@/lib/auth";

const ETAT_INITIAL: FormState = {};

function BoutonEnvoyer() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
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

      {etat.error ? (
        <p
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700"
        >
          {etat.error}
        </p>
      ) : null}

      <BoutonEnvoyer />
    </form>
  );
}
