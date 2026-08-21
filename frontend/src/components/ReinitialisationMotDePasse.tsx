"use client";

import { useActionState, useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { Check, Copy, KeyRound, RotateCcw } from "lucide-react";

import {
  reinitialiserMotDePasse,
  type ResultatReinitialisation,
} from "@/lib/securite-actions";

const ETAT_INITIAL: ResultatReinitialisation = {};

function Bouton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: "linear-gradient(135deg,#8a6d0b,#b8930f)" }}
    >
      <RotateCcw size={14} />
      {pending ? "جارٍ…" : "تعيين كلمة سر جديدة"}
    </button>
  );
}

/**
 * Reinitialisation d'un mot de passe par l'administration.
 *
 * L'ancien mot de passe n'est pas demande : on intervient precisement quand la
 * personne ne le connait plus.
 *
 * Le mot de passe produit s'affiche **une seule fois**. Il n'est stocke nulle
 * part en clair, et cet ecran est le seul endroit ou il apparaitra. D'ou le
 * bouton de copie : le recopier de tete est le meilleur moyen de le perdre.
 *
 * L'appelant monte ce composant avec `key={utilisateur}` : changer de personne
 * le recree a neuf, et le mot de passe de la precedente disparait de l'ecran
 * sans qu'aucun effet n'ait a le remettre a zero.
 */
export function ReinitialisationMotDePasse({
  utilisateur,
  nom,
  suggestion,
}: {
  utilisateur: number;
  nom: string;
  /** Valeur pre-remplie — pour une etudiante, son matricule ecrit deux fois. */
  suggestion?: string;
}) {
  const [etat, action] = useActionState(reinitialiserMotDePasse, ETAT_INITIAL);
  const [ouvert, setOuvert] = useState(false);
  const [copie, setCopie] = useState(false);

  useEffect(() => {
    if (!copie) return;
    const minuterie = setTimeout(() => setCopie(false), 2000);
    return () => clearTimeout(minuterie);
  }, [copie]);

  if (etat.motDePasse && ouvert) {
    return (
      <div className="rounded-xl border border-green-200 bg-green-50 px-3.5 py-3">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-green-800">
          <Check size={15} />
          تم تغيير كلمة سر {etat.nom || nom}
        </p>

        <div className="mt-2 flex items-center gap-2">
          <code
            dir="ltr"
            className="flex-1 rounded-lg border border-green-300 bg-white px-3 py-2 text-center text-lg font-bold tracking-wider text-dark"
          >
            {etat.motDePasse}
          </code>
          <button
            type="button"
            onClick={() => {
              navigator.clipboard?.writeText(etat.motDePasse!);
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
          هذه الكلمة تظهر مرة واحدة فقط. سلّميها لصاحبة الحساب، وسيُطلب منها
          تغييرها عند أول دخول.
        </p>

        <button
          type="button"
          onClick={() => setOuvert(false)}
          className="mt-2 text-xs font-medium text-green-800 underline"
        >
          إخفاء
        </button>
      </div>
    );
  }

  if (!ouvert) {
    return (
      <button
        type="button"
        onClick={() => setOuvert(true)}
        className="flex items-center gap-1.5 rounded-xl border border-gray-200 px-3.5 py-2 text-sm font-medium text-dark-soft transition-colors hover:bg-gray-50"
      >
        <KeyRound size={14} />
        تغيير كلمة السر
      </button>
    );
  }

  return (
    <form
      action={action}
      className="rounded-xl border border-gray-200 bg-gray-50 px-3.5 py-3"
    >
      <input type="hidden" name="utilisateur" value={utilisateur} />

      <p className="mb-2 text-sm font-medium text-dark">
        كلمة سر جديدة لـ {nom}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          name="new_password"
          dir="ltr"
          defaultValue={suggestion}
          minLength={8}
          placeholder="اتركيه فارغا لتوليد كلمة تلقائية"
          aria-label="كلمة السر الجديدة"
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
      </div>

      {etat.erreur ? (
        <p role="alert" className="mt-2 text-xs text-red-700">
          {etat.erreur}
        </p>
      ) : null}

      <p className="mt-2 text-xs leading-relaxed text-gris">
        ثمانية رموز على الأقل. الأرقام وحدها مقبولة — كلمة السر الأولى للطالبة
        هي رقمها مكتوبا مرتين. سيُطلب تغييرها عند أول دخول، ويُفتح الحساب إن كان
        مقفلا.
      </p>
    </form>
  );
}
