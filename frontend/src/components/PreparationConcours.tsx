"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import {
  Download,
  ListPlus,
  Play,
  Upload,
  UserPlus,
  Users,
} from "lucide-react";

import {
  ajouterGroupe,
  ajouterQuestions,
  demarrerCompetition,
  importerGroupes,
  importerQuestions,
  reserverPourLeDepartage,
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
  administre,
}: {
  competition: Competition;
  /** L'administration prepare les enonces ; le jury conduit la seance. */
  administre: boolean;
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
  const [etatFichier, actionFichier] = useActionState(
    importerQuestions,
    ETAT_INITIAL,
  );
  const [etatGroupesFichier, actionGroupesFichier] = useActionState(
    importerGroupes,
    ETAT_INITIAL,
  );
  const [etatReserve, actionReserve] = useActionState(
    reserverPourLeDepartage,
    ETAT_INITIAL,
  );

  const avecQuestions = competition.avec_questions;
  const groupes = competition.groups.length;
  const questions = competition.questions.length;

  // Une ندوة شعرية n'a rien a compter : elle tourne jusqu'a ce que le jury
  // l'arrete, et deux groupes suffisent a la commencer.
  //
  // Les questions gardees pour le departage sortent du calcul avant tout le
  // reste : c'est ce qui les rend reellement indisponibles au deroule.
  const gardees = competition.questions_reservees;
  const jolees =
    avecQuestions && groupes > 0
      ? Math.floor(Math.max(questions - gardees, 0) / groupes)
      : 0;
  const tours = jolees * groupes;
  const reserve = avecQuestions ? questions - tours : 0;
  const pret = groupes >= 2 && (!avecQuestions || jolees >= 1);

  return (
    <div className="space-y-5">
      {/* ─── Groupes ────────────────────────────────────────────── */}
      <Carte titre={`المجموعات (${groupes})`}>
        {competition.groups.length > 0 ? (
          <ul className="mb-4 grid gap-2 sm:grid-cols-2">
            {competition.groups.map((groupe) => (
              <li
                key={groupe.id}
                className="overflow-hidden rounded-xl border border-gray-100"
              >
                <p
                  className="px-3 py-1.5 text-sm font-semibold text-white"
                  style={{ background: groupe.color }}
                >
                  {groupe.name}
                </p>

                {/* La composition se relit ici, avant le depart : c'est le
                    seul moment ou elle peut encore etre corrigee. */}
                {groupe.members.length > 0 ? (
                  <ol className="divide-y divide-gray-50">
                    {groupe.members.map((membre) => (
                      <li
                        key={membre.id}
                        className="truncate px-3 py-1.5 text-sm text-dark-soft"
                      >
                        {membre.name}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="px-3 py-2 text-xs text-gris">لا أسماء بعد.</p>
                )}
              </li>
            ))}
          </ul>
        ) : null}

        {/* Le depot d'un classeur est reserve a l'administration : inscrire
            les participantes d'une classe entiere est un acte de preparation,
            pas de conduite. Le formulaire d'a cote reste ouvert au jury —
            c'est le rattrapage d'un oubli le jour meme. */}
        {administre ? (
          <>
            {/* Le classeur constitue les groupes et leurs listes d'un coup.
              Le formulaire d'a cote reste pour le groupe qu'on ajoute seul. */}
            <form
              key={`groupes-${groupes}`}
              action={actionGroupesFichier}
              className="mb-4 rounded-xl border border-dashed border-gray-200 bg-gray-50/60 p-4"
            >
              <input type="hidden" name="competition" value={competition.id} />

              <p className="flex items-center gap-1.5 text-sm font-medium text-dark-soft">
                <Users size={15} />
                استيراد القوائم من ملف Excel
              </p>
              <p className="mt-1 text-xs leading-relaxed text-gris">
                عمودان: اسم المجموعة ثم اسم الطالبة، سطر لكل طالبة. يتكرر اسم
                المجموعة في كل سطر من أسطرها.
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  type="file"
                  name="fichier"
                  accept=".xlsx"
                  required
                  className="min-w-0 flex-1 text-sm text-dark-soft file:me-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-primary"
                />
                <Bouton
                  libelle="استيراد"
                  enCours="جارٍ…"
                  icone={<Upload size={15} />}
                />
              </div>

              <a
                href="/modele-groupes.xlsx"
                download
                className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
              >
                <Download size={13} />
                تنزيل نموذج جاهز
              </a>
            </form>
            <Message etat={etatGroupesFichier} />
          </>
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
          vide laisserait croire a un oubli.

          Absentes aussi pour le jury : les enonces sont le fond du concours,
          ils se preparent en amont, et celui qui anime les decouvre en meme
          temps que la salle. */}
      {avecQuestions && administre ? (
        <Carte titre={`الأسئلة (${questions})`}>
          {/* Le classeur d'abord : c'est la voie qui porte les reponses, et
              celle qui coute le moins d'attention quand l'application tourne
              sur un serveur distant. La saisie collee reste dessous, pour la
              question qu'on ajoute au dernier moment.

              `key` sur le nombre de questions : le formulaire se remonte
              apres chaque import, sinon le champ garde le fichier deja
              depose et un second clic le rechargerait en double. */}
          <form
            key={`classeur-${questions}`}
            action={actionFichier}
            className="mb-5 rounded-xl border border-dashed border-gray-200 bg-gray-50/60 p-4"
          >
            <input type="hidden" name="competition" value={competition.id} />

            <p className="text-sm font-medium text-dark-soft">
              استيراد من ملف Excel
            </p>
            <p className="mt-1 text-xs leading-relaxed text-gris">
              عمودان: السؤال ثم الإجابة، سطر لكل سؤال. الإجابة اختيارية، ولا
              تظهر إلا في شاشة اللجنة.
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                type="file"
                name="fichier"
                accept=".xlsx"
                required
                className="min-w-0 flex-1 text-sm text-dark-soft file:me-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-primary"
              />
              <Bouton
                libelle="استيراد"
                enCours="جارٍ…"
                icone={<Upload size={15} />}
              />
            </div>

            <a
              href="/modele-questions.xlsx"
              download
              className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
            >
              <Download size={13} />
              تنزيل نموذج جاهز
            </a>
          </form>
          <Message etat={etatFichier} />

          <form action={actionQuestions} className="space-y-3">
            <input type="hidden" name="competition" value={competition.id} />
            <div>
              <label
                htmlFor="textes"
                className="mb-1.5 block text-sm font-medium text-dark-soft"
              >
                أو الصق الأسئلة: سؤال في كل سطر، بلا إجابات
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

          {/* Un nombre, et le compte se met a jour au-dessus.
              Sans ce reglage, ajouter des questions ne met rien de cote : le
              deroule les consomme par جولات entieres, et le reste — toujours
              plus petit que le nombre de groupes — ne suffit jamais a une
              manche de departage.

              Un nombre plutot qu'un oui-non : une manche consomme un enonce
              par groupe encore a egalite, et il en faut parfois plusieurs
              d'affilee. */}
          <form
            key={`reserve-${competition.questions_reservees}`}
            action={actionReserve}
            className="mt-4 rounded-xl border border-gray-100 bg-gray-50/60 p-3"
          >
            <input type="hidden" name="competition" value={competition.id} />
            <label
              htmlFor="questions_reservees"
              className="block text-sm font-medium text-dark-soft"
            >
              عدد الأسئلة المحجوزة لجولات الحسم
            </label>
            <p className="mt-1 text-xs leading-relaxed text-gris">
              تُترك جانبا ولا تُلعب. كل جولة حسم تستهلك سؤالا لكل مجموعة متعادلة
              {groupes > 0 && gardees > 0
                ? ` — ${gardees} سؤالا يكفي ${Math.floor(gardees / groupes)} جولة بخمس مجموعات`
                : ""}
              .
            </p>

            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input
                id="questions_reservees"
                name="questions_reservees"
                type="number"
                min={0}
                max={500}
                defaultValue={competition.questions_reservees}
                dir="ltr"
                className="champ w-28"
              />
              <Bouton
                libelle="حفظ"
                enCours="…"
                icone={<ListPlus size={15} />}
              />
            </div>
          </form>
          <Message etat={etatReserve} />

          {competition.questions.length > 0 ? (
            <ol className="mt-4 max-h-56 space-y-1.5 overflow-y-auto border-t border-gray-100 pt-3">
              {competition.questions.map((question, index) => (
                <li key={question.id} className="text-sm text-dark-soft">
                  <span className="chiffres text-xs text-gris">
                    {index + 1}.
                  </span>{" "}
                  {question.text}
                  {question.answer ? (
                    <span className="mt-0.5 block ps-4 text-xs text-primary">
                      ← {question.answer}
                    </span>
                  ) : null}
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
                  <Chiffre
                    libelle={
                      competition.questions_reservees > 0
                        ? "سؤالا لجولات الحسم"
                        : "سؤالا في الاحتياط"
                    }
                    valeur={reserve}
                  />
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
          /* Ne nommer que ce qui manque.
             Le message annoncait les deux conditions meme quand les groupes
             etaient au complet : on lisait « تحتاج المسابقة مجموعتين » avec
             six groupes a l'ecran, et on cherchait le probleme du mauvais
             cote. */
          <Alerte ton="warning">
            {groupes < 2 ? (
              avecQuestions ? (
                <>تحتاج المسابقة مجموعتين على الأقل.</>
              ) : (
                <>تحتاج الندوة مجموعتين على الأقل.</>
              )
            ) : (
              <>
                المجموعات جاهزة ({groupes}). تنقص الأسئلة: تحتاج {groupes} أسئلة
                على الأقل لجولة واحدة كاملة، وحاليا {questions}.
                {/* Le jury ne peut pas y remedier : lui dire ce qui manque
                    sans lui dire a qui s'adresser le laisserait chercher un
                    bouton qui n'existe pas pour lui. */}
                {administre ? "" : " راجعي الإدارة لإضافتها."}
              </>
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
