"use client";

import { useActionState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useFormStatus } from "react-dom";
import { Plus } from "lucide-react";

import { creerCompetition, type ResultatConcours } from "@/lib/concours-actions";

import { Carte } from "./ui";

const ETAT_INITIAL: ResultatConcours = {};

function Bouton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
    >
      <Plus size={15} />
      {pending ? "جارٍ الإنشاء…" : "مسابقة جديدة"}
    </button>
  );
}

/**
 * Creation d'une competition.
 *
 * Trois reglages seulement, parce que ce sont les seuls qui changent d'un
 * concours a l'autre. La duree est modifiable : trente secondes conviennent a
 * une question de memorisation, moins a une question de raisonnement.
 */
export function NouvelleCompetition() {
  const [etat, action] = useActionState(creerCompetition, ETAT_INITIAL);
  const router = useRouter();

  // Une fois creee, on enchaine sur sa preparation : c'est la suite evidente.
  useEffect(() => {
    if (etat.id) router.push(`/competitions/${etat.id}`);
  }, [etat.id, router]);

  return (
    <Carte titre="مسابقة جديدة">
      <form action={action} className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label
              htmlFor="name"
              className="mb-1.5 block text-sm font-medium text-dark-soft"
            >
              اسم المسابقة
            </label>
            <input
              id="name"
              name="name"
              type="text"
              required
              placeholder="مسابقة القرآن الكريم"
              className="champ"
            />
          </div>

          <div>
            <label
              htmlFor="turn_seconds"
              className="mb-1.5 block text-sm font-medium text-dark-soft"
            >
              مدة الدور بالثواني
            </label>
            <input
              id="turn_seconds"
              name="turn_seconds"
              type="number"
              min={5}
              max={600}
              defaultValue={30}
              dir="ltr"
              className="champ"
            />
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-dark-soft">
          <input
            type="checkbox"
            name="show_question"
            defaultChecked
            className="h-4 w-4 accent-primary"
          />
          عرض السؤال على شاشة القاعة
        </label>

        {etat.erreur ? (
          <p role="alert" className="text-sm text-red-700">
            {etat.erreur}
          </p>
        ) : null}

        <Bouton />
      </form>
    </Carte>
  );
}
