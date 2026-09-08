"use client";

import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import { Trash2 } from "lucide-react";

import {
  supprimerCompetition,
  type ResultatConcours,
} from "@/lib/concours-actions";

const ETAT_INITIAL: ResultatConcours = {};

function Confirmation() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-xl bg-red-700 px-3 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {pending ? "…" : "نعم، احذف"}
    </button>
  );
}

/**
 * Suppression d'une session, offerte a l'administration seule.
 *
 * Le bouton n'est rendu que pour un administrateur, mais ce n'est pas lui qui
 * protege la donnee : le serveur refuse la route a tout autre role. Le masquer
 * evite simplement de proposer une porte fermee.
 *
 * La confirmation se fait sur place, en deux temps, comme partout ailleurs
 * dans l'application. Un `confirm()` du navigateur serait plus court a ecrire,
 * mais il sort du cadre — et sur une tablette, en salle, on ne sait jamais
 * bien ou il s'affiche.
 */
export function SupprimerCompetition({
  competition,
  nom,
}: {
  competition: number;
  nom: string;
}) {
  const [etat, action] = useActionState(supprimerCompetition, ETAT_INITIAL);
  const [demande, setDemande] = useState(false);

  if (!demande) {
    return (
      <button
        type="button"
        onClick={() => setDemande(true)}
        title={`حذف ${nom}`}
        className="flex items-center gap-1.5 rounded-xl border border-red-200 px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-50"
      >
        <Trash2 size={14} />
        حذف
      </button>
    );
  }

  return (
    <form action={action} className="flex flex-wrap items-center gap-2">
      <input type="hidden" name="competition" value={competition} />
      <span className="text-xs text-dark-soft">
        تُحذف معها المجموعات والأدوار وقرارات اللجنة.
      </span>
      <button
        type="button"
        onClick={() => setDemande(false)}
        className="rounded-xl border border-gray-200 px-3 py-2 text-sm font-medium text-gris transition-colors hover:bg-gray-50"
      >
        تراجع
      </button>
      <Confirmation />
      {etat.erreur ? (
        <p role="alert" className="w-full text-xs text-red-700">
          {etat.erreur}
        </p>
      ) : null}
    </form>
  );
}
