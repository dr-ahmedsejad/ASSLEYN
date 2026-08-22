"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import { ChampMotDePasse } from "@/components/ChampMotDePasse";
import { changerMotDePasse, type FormState } from "@/lib/auth";
import { AIDE_MOT_DE_PASSE } from "@/lib/politique-mot-de-passe";

const ETAT_INITIAL: FormState = {};

const CHAMPS = [
  { nom: "current_password", libelle: "كلمة السر الحالية", auto: "current-password" },
  { nom: "new_password", libelle: "كلمة السر الجديدة", auto: "new-password" },
  { nom: "confirm_password", libelle: "تأكيد كلمة السر الجديدة", auto: "new-password" },
] as const;

function BoutonEnvoyer() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-60"
      style={{ background: "linear-gradient(135deg, #004d24, #006633)" }}
    >
      {pending ? "جارٍ الحفظ…" : "حفظ"}
    </button>
  );
}

export function FormulaireMotDePasse() {
  const [etat, action] = useActionState(changerMotDePasse, ETAT_INITIAL);

  return (
    <form action={action} className="space-y-4">
      {CHAMPS.map((champ) => (
        <ChampMotDePasse
          key={champ.nom}
          nom={champ.nom}
          libelle={champ.libelle}
          autoComplete={champ.auto}
        />
      ))}

      {/* Pas de `minLength` sur le champ : la validation native du navigateur
          afficherait son message dans la langue de son interface, au milieu
          d'un ecran arabe. La regle est rappelee ici, et verifiee — en arabe —
          par l'action et par le serveur. */}
      <p className="text-xs leading-relaxed text-gris">{AIDE_MOT_DE_PASSE}</p>

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
