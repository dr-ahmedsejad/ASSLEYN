"use client";

import { useActionState, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useFormStatus } from "react-dom";
import { Plus } from "lucide-react";

import {
  creerCompetition,
  type ResultatConcours,
} from "@/lib/concours-actions";
import type { TypeCompetition } from "@/lib/types";

import { Carte } from "./ui";

const ETAT_INITIAL: ResultatConcours = {};

/**
 * Les deux formes de session, telles qu'on les choisit.
 *
 * Le libelle ne suffit pas : « ندوة شعرية » ne dit pas de lui-meme qu'il n'y
 * aura rien a preparer. La phrase sous le titre le dit, au moment ou le choix
 * se fait — c'est la qu'elle sert, pas dans une aide qu'on ira lire apres.
 */
const TYPES: {
  valeur: TypeCompetition;
  titre: string;
  detail: string;
}[] = [
  {
    valeur: "CULTURELLE",
    titre: "مسابقة ثقافية",
    detail: "أسئلة تُحضَّر مسبقا، سؤال لكل دور.",
  },
  {
    valeur: "POETIQUE",
    titre: "ندوة شعرية",
    detail: "لا أسئلة: دور لكل مجموعة، وتُحتسب المشاركة.",
  },
];

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
 * Creation d'une session.
 *
 * Le type d'abord : c'est lui qui decide de tout le reste. Une مسابقة ثقافية
 * demandera des enonces et peut les projeter ; une ندوة شعرية n'a rien a
 * preparer et n'a pas de fin ecrite d'avance — elle tourne jusqu'a ce que le
 * jury l'arrete depuis sa console.
 *
 * La duree du tour reste modifiable dans les deux cas : trente secondes
 * conviennent a une question de memorisation, moins a un raisonnement, plus a
 * une recitation.
 */
export function NouvelleCompetition() {
  const [etat, action] = useActionState(creerCompetition, ETAT_INITIAL);
  const [type, setType] = useState<TypeCompetition>("CULTURELLE");
  const router = useRouter();

  // Une fois creee, on enchaine sur sa preparation : c'est la suite evidente.
  useEffect(() => {
    if (etat.id) router.push(`/competitions/${etat.id}`);
  }, [etat.id, router]);

  return (
    <Carte titre="مسابقة جديدة">
      <form action={action} className="space-y-3">
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-dark-soft">
            نوع المسابقة
          </legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {TYPES.map((choix) => (
              <label
                key={choix.valeur}
                className={`flex cursor-pointer gap-2.5 rounded-xl border p-3 transition-colors ${
                  type === choix.valeur
                    ? "border-primary bg-green-50"
                    : "border-gray-200 hover:bg-gray-50"
                }`}
              >
                <input
                  type="radio"
                  name="kind"
                  value={choix.valeur}
                  checked={type === choix.valeur}
                  onChange={() => setType(choix.valeur)}
                  className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
                />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-dark">
                    {choix.titre}
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-gris">
                    {choix.detail}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

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

        {type === "POETIQUE" ? (
          <p className="text-xs leading-relaxed text-gris">
            تدور الندوة على المجموعات جولة بعد جولة، وتنتهي عندما تُنهيها اللجنة
            من شاشة الإدارة. لا عدد جولات يُحدَّد مسبقا.
          </p>
        ) : (
          <label className="flex items-center gap-2 text-sm text-dark-soft">
            <input
              type="checkbox"
              name="show_question"
              defaultChecked
              className="h-4 w-4 accent-primary"
            />
            عرض السؤال على شاشة القاعة
          </label>
        )}

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
