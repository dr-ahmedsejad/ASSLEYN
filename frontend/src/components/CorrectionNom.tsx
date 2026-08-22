"use client";

import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import { Check, Pencil } from "lucide-react";

import { corrigerIdentite, type ResultatIdentite } from "@/lib/comptes-actions";

const ETAT_INITIAL: ResultatIdentite = {};

function Bouton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
    >
      <Check size={14} />
      {pending ? "…" : "حفظ"}
    </button>
  );
}

/**
 * Correction du nom d'un compte.
 *
 * Les premiers comptes ont ete ouverts sans champ de nom : leur libelle etait
 * une translitteration de l'identifiant — « sejad » devenu « سيداد ». Une
 * personne doit pouvoir porter son nom tel qu'elle l'ecrit.
 *
 * Pour une etudiante, la correction suit jusqu'a son dossier : le compte et le
 * dossier ne peuvent pas porter deux noms differents.
 *
 * L'appelant monte ce composant avec `key={utilisateur}` — changer de personne
 * le recree, champ vierge et message efface.
 */
export function CorrectionNom({
  utilisateur,
  nom,
}: {
  utilisateur: number;
  nom: string;
}) {
  const [etat, action] = useActionState(corrigerIdentite, ETAT_INITIAL);
  const [ouvert, setOuvert] = useState(false);

  if (!ouvert) {
    return (
      <button
        type="button"
        onClick={() => setOuvert(true)}
        aria-label="تعديل الاسم"
        title="تعديل الاسم"
        className="flex h-7 w-7 items-center justify-center rounded-lg text-gris transition-colors hover:bg-gray-50 hover:text-dark"
      >
        <Pencil size={13} />
      </button>
    );
  }

  return (
    <form action={action} className="flex flex-wrap items-center gap-2">
      <input type="hidden" name="utilisateur" value={utilisateur} />
      <input
        type="text"
        name="full_name_ar"
        defaultValue={nom}
        required
        autoFocus
        aria-label="الاسم الكامل"
        className="champ max-w-xs"
      />
      <Bouton />
      <button
        type="button"
        onClick={() => setOuvert(false)}
        className="rounded-xl border border-gray-200 bg-white px-3.5 py-2 text-sm text-gris transition-colors hover:bg-gray-50"
      >
        إلغاء
      </button>
      {etat.erreur ? (
        <span role="alert" className="text-xs text-red-700">
          {etat.erreur}
        </span>
      ) : null}
    </form>
  );
}
