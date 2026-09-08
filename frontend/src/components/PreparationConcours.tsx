"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { ListPlus, Play, UserPlus } from "lucide-react";

import {
  ajouterGroupe,
  ajouterQuestions,
  demarrerCompetition,
  type ResultatConcours,
} from "@/lib/concours-actions";
import type { Competition } from "@/lib/types";

import { LienDirect } from "@/components/LienDirect";

import { Alerte, Carte } from "./ui";

const ETAT_INITIAL: ResultatConcours = {};

function Bouton({
  libelle,
  enCours,
  icone,
  ton = "vert",
}: {
  libelle: string;
  enCours: string;
  icone: React.ReactNode;
  ton?: "vert" | "or";
}) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex items-center justify-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      style={{
        background:
          ton === "or"
            ? "linear-gradient(135deg,#8a6d0b,#b8930f)"
            : "linear-gradient(135deg,#006633,#008844)",
      }}
    >
      {icone}
      {pending ? enCours : libelle}
    </button>
  );
}

function Message({ etat }: { etat: ResultatConcours }) {
  if (etat.erreur) {
    return (
      <p role="alert" className="mt-2 text-sm text-red-700">
        {etat.erreur}
      </p>
    );
  }
  if (etat.message) {
    return <p className="mt-2 text-sm text-primary">{etat.message}</p>;
  }
  return null;
}

/**
 * Preparation d'une competition.
 *
 * Trois gestes dans l'ordre ou ils se posent : nommer les groupes, coller les
 * questions, lancer. Le troisieme fige le deroule — apres lui, plus rien ne
 * bouge, parce que le jury doit pouvoir travailler sans reseau et qu'un
 * programme qui change sous ses pieds le rendrait faux.
 */
export function PreparationConcours({
  competition,
}: {
  competition: Competition;
}) {
  const [etatGroupe, actionGroupe] = useActionState(
    ajouterGroupe,
    ETAT_INITIAL,
  );
  const [etatQuestions, actionQuestions] = useActionState(
    ajouterQuestions,
    ETAT_INITIAL,
  );
  const [etatDepart, actionDepart] = useActionState(
    demarrerCompetition,
    ETAT_INITIAL,
  );

  const avecQuestions = competition.avec_questions;
  const groupes = competition.groups.length;
  const questions = competition.questions.length;

  // Une ندوة شعرية n'a rien a compter : elle tourne jusqu'a ce que le jury
  // l'arrete, et deux groupes suffisent a la commencer.
  const jolees =
    avecQuestions && groupes > 0 ? Math.floor(questions / groupes) : 0;
  const tours = jolees * groupes;
  const reserve = avecQuestions ? questions - tours : 0;
  const pret = groupes >= 2 && (!avecQuestions || jolees >= 1);

  return (
    <div className="space-y-5">
      {/* ─── Groupes ────────────────────────────────────────────── */}
      <Carte titre={`المجموعات (${groupes})`}>
        {competition.groups.length > 0 ? (
          <ul className="mb-4 flex flex-wrap gap-2">
            {competition.groups.map((groupe) => (
              <li
                key={groupe.id}
                className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm font-semibold text-white"
                style={{ background: groupe.color }}
              >
                {groupe.name}
              </li>
            ))}
          </ul>
        ) : null}

        {/* `key` sur le nombre de groupes : le formulaire se remonte apres
            chaque ajout, et le champ repart vide. Sans cela le nom precedent
            restait, et deux groupes ajoutes de suite se retrouvaient colles
            dans un seul nom. */}
        <form
          key={groupes}
          action={actionGroupe}
          className="flex flex-wrap items-end gap-2"
        >
          <input type="hidden" name="competition" value={competition.id} />
          <input type="hidden" name="rang" value={groupes} />
          <div className="min-w-0 flex-1">
            <label
              htmlFor="groupe"
              className="mb-1.5 block text-sm font-medium text-dark-soft"
            >
              اسم المجموعة
            </label>
            <input
              id="groupe"
              name="name"
              type="text"
              required
              placeholder="مجموعة الحافظات"
              className="champ"
            />
          </div>
          <Bouton libelle="إضافة" enCours="…" icone={<UserPlus size={15} />} />
        </form>
        <Message etat={etatGroupe} />
      </Carte>

      {/* ─── Questions ──────────────────────────────────────────────
          Absentes de la ندوة شعرية : il n'y a rien a y preparer, et une carte
          vide laisserait croire a un oubli. */}
      {avecQuestions ? (
        <Carte titre={`الأسئلة (${questions})`}>
          <form action={actionQuestions} className="space-y-3">
            <input type="hidden" name="competition" value={competition.id} />
            <div>
              <label
                htmlFor="textes"
                className="mb-1.5 block text-sm font-medium text-dark-soft"
              >
                سؤال في كل سطر
              </label>
              <textarea
                id="textes"
                name="textes"
                rows={6}
                required
                placeholder={
                  "ما حكم النون الساكنة إذا جاء بعدها حرف الباء؟\nمن كتب المعلقات السبع؟"
                }
                className="champ"
                style={{ resize: "vertical" }}
              />
            </div>
            <Bouton
              libelle="إضافة الأسئلة"
              enCours="جارٍ…"
              icone={<ListPlus size={15} />}
            />
          </form>
          <Message etat={etatQuestions} />

          {competition.questions.length > 0 ? (
            <ol className="mt-4 max-h-56 space-y-1.5 overflow-y-auto border-t border-gray-100 pt-3">
              {competition.questions.map((question, index) => (
                <li key={question.id} className="text-sm text-dark-soft">
                  <span className="chiffres text-xs text-gris">
                    {index + 1}.
                  </span>{" "}
                  {question.text}
                </li>
              ))}
            </ol>
          ) : null}
        </Carte>
      ) : null}

      {/* ─── Depart ─────────────────────────────────────────────── */}
      <Carte titre="الانطلاق">
        {pret ? (
          <>
            <div
              className={`mb-4 grid gap-3 text-center ${
                avecQuestions ? "grid-cols-3" : "grid-cols-1"
              }`}
            >
              {avecQuestions ? (
                <>
                  <Chiffre libelle="جولة" valeur={jolees} />
                  <Chiffre libelle="دورا" valeur={tours} />
                  <Chiffre libelle="سؤالا في الاحتياط" valeur={reserve} />
                </>
              ) : (
                <Chiffre libelle="مجموعات في كل جولة" valeur={groupes} />
              )}
            </div>

            {reserve > 0 ? (
              <div className="mb-4">
                <Alerte ton="info">
                  {reserve} سؤالا يبقى في الاحتياط: كل مجموعة تجيب على العدد
                  نفسه من الأسئلة، وإلا صار الترتيب محل نقاش.
                </Alerte>
              </div>
            ) : null}

            <form action={actionDepart}>
              <input type="hidden" name="competition" value={competition.id} />
              <input
                type="hidden"
                name="avec_questions"
                value={avecQuestions ? "1" : ""}
              />
              <Bouton
                libelle={avecQuestions ? "انطلاق المسابقة" : "انطلاق الندوة"}
                enCours="جارٍ الانطلاق…"
                icone={<Play size={16} />}
                ton="or"
              />
            </form>
            <Message etat={etatDepart} />

            <p className="mt-3 text-xs leading-relaxed text-gris">
              {avecQuestions
                ? "بعد الانطلاق لا تُعدَّل المجموعات ولا الأسئلة: البرنامج يُحمَّل كاملا في جهاز اللجنة ليعمل دون شبكة."
                : "بعد الانطلاق لا تُعدَّل المجموعات: البرنامج يُحمَّل كاملا في جهاز اللجنة ليعمل دون شبكة. تدور الندوة جولة بعد جولة حتى تُنهيها اللجنة من شاشة الإدارة."}
            </p>

            {/* Le lien est disponible des la preparation : on l'envoie a la
                salle, ou on l'ouvre sur le videoprojecteur, avant de lancer. */}
            <div className="mt-4">
              <LienDirect code={competition.code} />
            </div>
          </>
        ) : (
          <Alerte ton="warning">
            {avecQuestions ? (
              <>
                تحتاج المسابقة مجموعتين على الأقل، وأسئلة تكفي لجولة كاملة
                {groupes >= 2 ? ` (${groupes} أسئلة على الأقل)` : ""}.
              </>
            ) : (
              <>تحتاج الندوة مجموعتين على الأقل.</>
            )}
          </Alerte>
        )}
      </Carte>
    </div>
  );
}

function Chiffre({ libelle, valeur }: { libelle: string; valeur: number }) {
  return (
    <div className="rounded-xl bg-green-50 px-3 py-3">
      <p className="chiffres text-2xl font-bold text-primary">{valeur}</p>
      <p className="mt-0.5 text-[11px] text-gris">{libelle}</p>
    </div>
  );
}
