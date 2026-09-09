"use client";

import {
  useActionState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle2,
  CloudOff,
  Eye,
  Flag,
  Swords,
  Play,
  TimerOff,
  Volume2,
  VolumeX,
  XCircle,
} from "lucide-react";

import { LienDirect } from "@/components/LienDirect";
import { Medaille } from "@/components/Medaille";
import { classerLocalement, groupesADepartager } from "@/lib/classement";
import { cloturerCompetition, lancerBarrage } from "@/lib/concours-actions";
import { empiler, identifiant, refuses, vider } from "@/lib/file-hors-ligne";
import {
  arreter as arreterLesSons,
  definirMuet,
  estMuet,
  programmerTour,
} from "@/lib/sons";
import type { DerouleConcours, Tour } from "@/lib/types";

import { Alerte, Carte } from "./ui";

/**
 * Console du jury.
 *
 * Toute la competition tient dans cet ecran, et il est concu pour une salle :
 * un seul geste possible a la fois, des cibles larges, aucune information qui
 * ne serve au tour en cours.
 *
 * Le point delicat n'est pas l'affichage mais le temps. Le compte a rebours ne
 * demande rien au reseau : le serveur a donne l'heure de depart du tour **et**
 * la sienne au chargement ; l'ecart entre les deux est mesure une fois, puis
 * le decompte tourne sur l'horloge locale. Coupez la connexion, il reste juste.
 *
 * Les gestes, eux, passent par une file : ecrits localement, envoyes ensuite.
 * Le jury n'attend jamais le reseau pour avancer.
 */
export function ConsoleConcours({ deroule }: { deroule: DerouleConcours }) {
  const { competition } = deroule;

  const [tours, setTours] = useState<Tour[]>(deroule.tours);
  const [enAttente, setEnAttente] = useState(0);
  // Gestes refuses par le serveur. Ils ne se rattrapent pas : le jury
  // doit l'apprendre pendant la seance, pas apres.
  const [rejetes, setRejetes] = useState(0);
  const [motif, setMotif] = useState("");

  /**
   * Le son est-il coupe ?
   *
   * `false` au premier rendu, puis relu depuis l'appareil dans un effet : le
   * serveur ne connait pas ce reglage, et lire le stockage pendant le rendu
   * ferait diverger le HTML envoye de celui que le navigateur reconstruit.
   */
  const [muet, setMuet] = useState(false);
  useEffect(() => setMuet(estMuet("jury")), []);
  const [restantMesure, setRestant] = useState(competition.turn_seconds);

  /**
   * Ecart entre l'horloge du serveur et celle de cette tablette.
   *
   * L'heure d'un telephone peut avoir des minutes de retard ; une duree, elle,
   * ne ment pas. On mesure donc l'ecart une fois, puis on decompte localement.
   *
   * Il est lu dans les effets et les gestes, jamais pendant le rendu : le
   * rendu doit rester une fonction de son etat, sans quoi deux affichages
   * successifs du meme etat pourraient differer.
   */
  const ecart = useRef<number | null>(null);

  const heureServeur = useCallback(
    () => new Date(Date.now() + (ecart.current ?? 0)),
    [],
  );

  // Reprise de la file : a l'ouverture, au retour du reseau, puis
  // regulierement tant qu'il reste des gestes en attente.
  const reprendre = useCallback(async () => {
    const restants = await vider();
    setEnAttente(restants);
    setRejetes(refuses().length);
  }, []);

  useEffect(() => {
    const amorce = setTimeout(() => void reprendre(), 0);
    const rythme = setInterval(() => void reprendre(), 5000);
    const auRetour = () => void reprendre();
    window.addEventListener("online", auRetour);
    return () => {
      clearTimeout(amorce);
      clearInterval(rythme);
      window.removeEventListener("online", auRetour);
    };
  }, [reprendre]);

  const courant = useMemo(
    () => tours.find((t) => t.outcome === "PENDING") ?? null,
    [tours],
  );

  // Le classement vit dans son propre module : il doit rester identique a
  // celui du serveur, et cette egalite se verifie mieux sur trente lignes
  // isolees que sur un composant entier.
  const classement = useMemo(() => classerLocalement(tours), [tours]);

  // Qui reste a departager, d'apres les scores que la console tient elle-meme.
  // Le serveur ne peut pas le dire : entre le chargement de la page et la fin
  // de la seance, le jury a joue quinze tours sans rien lui envoyer.
  const egalite = useMemo(() => groupesADepartager(classement), [classement]);

  // Battement du compte a rebours. Tout le calcul du temps vit ici : c'est le
  // seul endroit ou lire l'horloge est legitime.
  const depart = courant?.started_at ?? null;
  useEffect(() => {
    if (ecart.current === null) {
      ecart.current = new Date(deroule.maintenant).getTime() - Date.now();
    }
    if (!depart) return;
    const battement = setInterval(() => {
      const ecoule =
        (Date.now() + (ecart.current ?? 0) - new Date(depart).getTime()) / 1000;
      setRestant(Math.max(competition.turn_seconds - Math.floor(ecoule), 0));
    }, 250);
    return () => clearInterval(battement);
  }, [depart, competition.turn_seconds, deroule.maintenant]);

  /**
   * Les sons du tour.
   *
   * Poses d'un coup au demarrage, sur l'horloge audio, a partir des memes
   * deux valeurs qui font le compte a rebours — l'heure de depart et l'ecart
   * avec l'horloge du serveur. La pulsation tombe donc exactement sur le
   * changement de chiffre, et le reste jusqu'a la fin du tour.
   *
   * Le nettoyage coupe tout : une decision prise avant l'expiration fait
   * changer de tour, et les pulsations restantes n'ont plus lieu d'etre.
   */
  useEffect(() => {
    if (!depart || muet) return;
    programmerTour({
      debut: depart,
      secondes: competition.turn_seconds,
      ecart: ecart.current ?? 0,
      ecran: "jury",
    });
    return () => arreterLesSons();
  }, [depart, muet, competition.turn_seconds]);

  // Tant que le tour n'a pas demarre, la duree pleine se deduit : inutile de
  // la poser dans l'etat, et l'y poser depuis un effet serait une mise a jour
  // synchrone de plus.
  const restant = depart ? restantMesure : competition.turn_seconds;
  const enMarche = Boolean(courant?.started_at);
  const expire = enMarche && restant === 0;
  // Les manches de departage ne font pas partie du programme : les compter
  // ferait afficher « 15 / 17 » ici et « 15 / 15 » sur l'ecran de la salle.
  const ordinaires = tours.filter((t) => t.tiebreak_round === 0);
  const joues = ordinaires.filter((t) => t.outcome !== "PENDING").length;

  function lancer() {
    if (!courant || courant.started_at) return;
    const depart = heureServeur().toISOString();
    empiler(`tours/${courant.id}/lancer`, {
      client_uuid: identifiant(),
      demarre_a: depart,
    });
    setTours((liste) =>
      liste.map((t) =>
        t.id === courant.id ? { ...t, started_at: depart } : t,
      ),
    );
    void reprendre();
  }

  function trancher(outcome: "CORRECT" | "NO_ANSWER") {
    if (!courant || !courant.started_at) return;
    const instant = heureServeur().toISOString();
    empiler(`tours/${courant.id}/decider`, {
      client_uuid: identifiant(),
      outcome,
      decide_a: instant,
      note: motif.trim(),
    });
    setTours((liste) =>
      liste.map((t) =>
        t.id === courant.id
          ? {
              ...t,
              outcome,
              decided_at: instant,
              awarded_late: outcome === "CORRECT" && expire,
              note: motif.trim(),
            }
          : t,
      ),
    );
    setMotif("");
    void reprendre();
  }

  // ─── Competition terminee ────────────────────────────────────────
  if (!courant) {
    return (
      <div className="space-y-5">
        <Carte
          titre={competition.avec_questions ? "انتهت المسابقة" : "انتهت الندوة"}
        >
          <p className="text-sm text-gris">
            {competition.avec_questions
              ? "كل الأدوار حُسمت. النتيجة النهائية معروضة أدناه، وهي نفسها التي تظهر على شاشة القاعة."
              : "أنهت اللجنة الندوة. النتيجة النهائية معروضة أدناه، وهي نفسها التي تظهر على شاشة القاعة."}
          </p>
        </Carte>
        {/* Un seul bouton, et rien a regler.
            Le serveur sait qui est a egalite et avec quoi la departager ; le
            jury n'a qu'a decider s'il le veut. */}
        {egalite.length > 1 ? (
          <Departage
            competition={competition.id}
            groupes={egalite.map((ligne) => ligne.name)}
            avecEnonces={deroule.departage.reserve >= egalite.length}
          />
        ) : null}

        <Classement lignes={classement} final />
        <LienDirect code={competition.code} />
      </div>
    );
  }

  // Le deroule porte la composition des groupes ; le tour ne porte que
  // l'identifiant du sien.
  const membres =
    competition.groups.find((g) => g.id === courant.group)?.members.map(
      (m) => m.name,
    ) ?? [];

  const fraction = restant / competition.turn_seconds;

  return (
    <div className="space-y-4">
      {enAttente > 0 ? (
        <Alerte ton="warning">
          <span className="flex items-center gap-2">
            <CloudOff size={15} />
            <span className="chiffres">
              {enAttente} عملية في الانتظار — الاتصال منقطع. لا شيء يضيع، سيُرسل
              كل شيء عند عودة الشبكة.
            </span>
          </span>
        </Alerte>
      ) : null}

      {/*
        Un geste refuse ne se rattrape pas : le serveur l'a ecarte, et le
        rejouer donnerait le meme refus. Le dire tout de suite est la seule
        chose utile — sans quoi le jury anime une seance entiere pendant que
        la salle reste immobile.
      */}
      {rejetes > 0 ? (
        <Alerte ton="danger">
          <span className="flex items-center gap-2">
            <AlertTriangle size={15} />
            <span className="chiffres">
              {rejetes} عملية رفضها الخادم ولم تُسجَّل. أعِد تحميل الصفحة
              للاطلاع على الحالة الحقيقية قبل المتابعة.
            </span>
          </span>
        </Alerte>
      ) : null}

      {/* ─── Le tour en cours ─────────────────────────────────────── */}
      <div
        className="overflow-hidden rounded-3xl border shadow-card-lg"
        style={{ borderColor: `${courant.group_color}33`, background: "#fff" }}
      >
        <div
          className="px-5 py-4 text-center text-white"
          style={{
            background: `linear-gradient(160deg, ${courant.group_color}, ${courant.group_color}cc)`,
          }}
        >
          {/* Une ندوة شعرية n'a pas de dernier tour : annoncer « الدور 3 من
              75 » ferait passer la reserve preparee pour un programme. */}
          <p className="chiffres text-[11px] opacity-80">
            {courant.tiebreak_round > 0
              ? `جولة الحسم ${courant.tiebreak_round}`
              : `الجولة ${courant.round_number} · الدور ${courant.index + 1}` +
                (competition.avec_questions ? ` من ${tours.length}` : "")}
          </p>
          <p className="mt-0.5 text-2xl font-bold leading-tight">
            {courant.group_name}
          </p>

          {/* La composition, pour appeler les participantes par leur nom. */}
          {membres.length > 0 ? (
            <p className="mt-1 text-xs leading-relaxed opacity-85">
              {membres.join(" · ")}
            </p>
          ) : null}
        </div>

        <div className="flex flex-col items-center gap-5 p-5">
          {/* Pas d'enonce dans une ندوة شعرية : le tour de parole s'ouvre sur
              le chronometre, et le jury ecoute. */}
          {courant.question_text ? (
            <div className="w-full">
              <p className="text-center text-xl font-semibold leading-relaxed text-dark">
                {courant.question_text}
              </p>

              {/* La reponse, quand le classeur en portait une.
                  Elle n'apparait que sur cet ecran — celui du jury — et
                  jamais sur celui de la salle, qui ne la recoit meme pas.
                  Elle ne decide de rien : le point reste accorde a la main,
                  parce qu'une reponse juste peut etre dite autrement que ce
                  qui a ete tape la veille dans un tableur. */}
              {courant.question_answer ? (
                <div className="mt-3 rounded-xl border border-primary/25 bg-green-50/70 px-3 py-2">
                  <p className="flex items-center gap-1.5 text-[11px] font-bold text-primary">
                    <Eye size={12} />
                    الإجابة — لا تظهر في شاشة القاعة
                  </p>
                  <p className="mt-0.5 text-base leading-relaxed text-dark-soft">
                    {courant.question_answer}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-col items-center gap-2">
            <Chronometre
              secondes={restant}
              fraction={fraction}
              enMarche={enMarche}
              couleur={courant.group_color}
            />

            {/* Une salle petite, une seance filmee, une reunion a cote : le
                son doit pouvoir se taire d'un geste, et le choix rester pris
                pour les tours suivants. */}
            <button
              type="button"
              onClick={() => {
                const suivant = !muet;
                setMuet(suivant);
                definirMuet("jury", suivant);
              }}
              aria-pressed={muet}
              className="flex items-center gap-1.5 rounded-full border border-gray-200 px-3 py-1 text-xs font-medium text-gris transition-colors hover:bg-gray-50"
            >
              {muet ? <VolumeX size={13} /> : <Volume2 size={13} />}
              {muet ? "الصوت مكتوم" : "الصوت يعمل"}
            </button>
          </div>

          {!enMarche ? (
            <button
              type="button"
              onClick={lancer}
              className="flex w-full items-center justify-center gap-2 rounded-2xl px-6 py-5 text-lg font-bold text-white shadow-card transition-opacity hover:opacity-90"
              style={{ background: "linear-gradient(135deg,#004d24,#006633)" }}
            >
              <Play size={20} />
              ابدأ الدور
            </button>
          ) : (
            <div className="grid w-full gap-3">
              <button
                type="button"
                onClick={() => trancher("CORRECT")}
                className="flex items-center justify-center gap-2 rounded-2xl px-6 py-5 text-lg font-bold text-white shadow-card transition-opacity hover:opacity-90"
                style={{
                  background: expire
                    ? "linear-gradient(135deg,#8a6d0b,#b8930f)"
                    : "linear-gradient(135deg,#006633,#008844)",
                }}
              >
                <CheckCircle2 size={20} />
                {/* Une ندوة شعرية ne juge pas la justesse d'une reponse : le
                    jury constate seulement que le groupe a pris la parole. */}
                {competition.avec_questions
                  ? expire
                    ? "إجابة صحيحة رغم انتهاء الوقت"
                    : "إجابة صحيحة"
                  : expire
                    ? "أجابت رغم انتهاء الوقت"
                    : "أجابت"}
              </button>

              {/* « لم تجب » ne s'ouvre qu'a l'expiration du temps.
                  Tant qu'il reste des secondes, le groupe peut encore
                  repondre : declarer l'absence de reponse avant la fin
                  reviendrait a lui retirer son tour. */}
              <button
                type="button"
                onClick={() => trancher("NO_ANSWER")}
                disabled={!expire}
                className="flex items-center justify-center gap-2 rounded-2xl border-2 border-gray-200 px-6 py-4 text-base font-bold text-gris transition-colors enabled:hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <XCircle size={18} />
                لم تجب
              </button>

              {!expire ? (
                <p className="chiffres -mt-1 text-center text-xs text-gris">
                  يُفعَّل زر «لم تجب» بعد انتهاء الوقت — تبقى {restant} ثانية
                </p>
              ) : null}
            </div>
          )}

          {/* Le motif n'apparait que lorsqu'il devient utile : accorder un
              point apres l'expiration est une decision, elle se justifie. */}
          {expire ? (
            <div className="w-full">
              <label
                htmlFor="motif"
                className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-dark-soft"
              >
                <TimerOff size={13} />
                سبب المنح بعد انتهاء الوقت (اختياري، يُحفظ في السجل)
              </label>
              <input
                id="motif"
                type="text"
                value={motif}
                onChange={(e) => setMotif(e.target.value)}
                placeholder="أجابت في الوقت، انقطع الاتصال"
                className="champ"
              />
            </div>
          ) : null}
        </div>
      </div>

      <Classement lignes={classement} />

      <p className="chiffres text-center text-xs text-gris">
        {competition.avec_questions
          ? `${joues} / ${ordinaires.length} دورا`
          : `${joues} دورا`}
      </p>

      {/* La ندوة شعرية ne s'arrete pas toute seule : c'est le jury qui decide
          que la seance est finie, et il n'y a que cet ecran pour le dire. */}
      {!competition.avec_questions ? (
        <ClotureNdwa competition={competition.id} />
      ) : null}

      <LienDirect code={competition.code} />
    </div>
  );
}

/**
 * Le departage, propose a la fin quand une egalite subsiste.
 *
 * Rien a regler : le serveur choisit l'egalite la plus haute et l'alimente
 * comme il peut. Le jury lit qui joue, et decide s'il lance. Il relancera
 * autant de fois qu'il le veut — souvent deux, le temps de former le podium.
 */
function Departage({
  competition,
  groupes,
  avecEnonces,
}: {
  competition: number;
  groupes: string[];
  avecEnonces: boolean;
}) {
  const [etat, action] = useActionState(lancerBarrage, {});
  const router = useRouter();

  // La console travaille sur une copie locale du deroule ; une fois la manche
  // creee, c'est le serveur qui a raison.
  useEffect(() => {
    if (etat.message) router.refresh();
  }, [etat.message, router]);

  return (
    <Carte titre="تعادل">
      <p className="text-sm leading-relaxed text-dark-soft">
        {groupes.join(" · ")} — بالنقاط نفسها.
      </p>
      <p className="mt-1 text-xs leading-relaxed text-gris">
        {avecEnonces
          ? "جولة الحسم تأخذ أسئلتها من الاحتياط: دور واحد لكل مجموعة."
          : "لا أسئلة في الاحتياط: اطرحي السؤال بصوتك، والمؤقّت يعمل كالعادة."}
      </p>

      <form action={action} className="mt-3">
        <input type="hidden" name="competition" value={competition} />
        <button
          type="submit"
          className="flex w-full items-center justify-center gap-2 rounded-2xl px-6 py-4 text-base font-bold text-white shadow-card transition-opacity hover:opacity-90"
          style={{ background: "linear-gradient(135deg,#8a6d0b,#b8930f)" }}
        >
          <Swords size={18} />
          جولة الحسم
        </button>
      </form>

      {etat.erreur ? (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {etat.erreur}
        </p>
      ) : null}
    </Carte>
  );
}

/**
 * Fin de la ندوة شعرية.
 *
 * Rien d'autre ne l'arrete : ni les questions, puisqu'il n'y en a pas, ni un
 * nombre de جولات, puisqu'on n'en fixe pas. Le bouton demande donc une
 * confirmation — un geste isole, irreversible, au milieu d'un ecran ou tous
 * les autres se rattrapent.
 */
function ClotureNdwa({ competition }: { competition: number }) {
  const [etat, action] = useActionState(cloturerCompetition, {});
  const [confirme, setConfirme] = useState(false);
  const router = useRouter();

  // La console travaille sur son etat local ; une fois la seance close, c'est
  // le serveur qui a raison — on lui redemande la page.
  useEffect(() => {
    if (etat.message) router.refresh();
  }, [etat.message, router]);

  if (!confirme) {
    return (
      <button
        type="button"
        onClick={() => setConfirme(true)}
        className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-gray-200 px-6 py-3.5 text-sm font-bold text-gris transition-colors hover:bg-gray-50"
      >
        <Flag size={16} />
        إنهاء الندوة
      </button>
    );
  }

  return (
    <form action={action} className="space-y-2">
      <input type="hidden" name="competition" value={competition} />
      <p className="text-center text-sm text-dark-soft">
        هل تُنهي الندوة؟ الترتيب يصير نهائيا.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setConfirme(false)}
          className="rounded-2xl border-2 border-gray-200 px-4 py-3 text-sm font-bold text-gris transition-colors hover:bg-gray-50"
        >
          تراجع
        </button>
        <button
          type="submit"
          className="flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-bold text-white transition-opacity hover:opacity-90"
          style={{ background: "linear-gradient(135deg,#8a6d0b,#b8930f)" }}
        >
          <Flag size={16} />
          نعم، أنهِ الندوة
        </button>
      </div>
      {etat.erreur ? (
        <p role="alert" className="text-center text-sm text-red-700">
          {etat.erreur}
        </p>
      ) : null}
    </form>
  );
}

/**
 * Compte a rebours.
 *
 * Un anneau plutot qu'un nombre seul : de loin, et sous tension, une forme se
 * lit avant un chiffre. Il vire a l'ambre sous dix secondes, au rouge a zero —
 * sans clignoter, ce qui rendrait la salle nerveuse pour rien.
 */
function Chronometre({
  secondes,
  fraction,
  enMarche,
  couleur,
}: {
  secondes: number;
  fraction: number;
  enMarche: boolean;
  couleur: string;
}) {
  const rayon = 62;
  const perimetre = 2 * Math.PI * rayon;
  const teinte = !enMarche
    ? "#cbd5e1"
    : secondes === 0
      ? "#c82020"
      : secondes <= 10
        ? "#b8930f"
        : couleur;

  return (
    <div className="relative flex h-40 w-40 items-center justify-center">
      <svg viewBox="0 0 160 160" className="absolute inset-0 -rotate-90">
        <circle
          cx="80"
          cy="80"
          r={rayon}
          fill="none"
          stroke="#eef2f5"
          strokeWidth="12"
        />
        <circle
          cx="80"
          cy="80"
          r={rayon}
          fill="none"
          stroke={teinte}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={perimetre}
          strokeDashoffset={perimetre * (1 - Math.max(fraction, 0))}
          style={{ transition: "stroke-dashoffset .3s linear, stroke .3s" }}
        />
      </svg>
      <div className="text-center">
        <p
          className="chiffres text-5xl font-extrabold leading-none tabular-nums"
          style={{ color: teinte }}
        >
          {secondes}
        </p>
        <p className="mt-1 text-[11px] text-gris">
          {!enMarche
            ? "بانتظار الانطلاق"
            : secondes === 0
              ? "انتهى الوقت"
              : "ثانية"}
        </p>
      </div>
    </div>
  );
}

function Classement({
  lignes,
  final = false,
}: {
  lignes: {
    name: string;
    color: string;
    points: number;
    rank: number;
    separe: boolean;
  }[];
  final?: boolean;
}) {
  const maximum = Math.max(...lignes.map((l) => l.points), 1);
  return (
    <Carte titre={final ? "النتيجة النهائية" : "النقاط"}>
      <ul className="space-y-2.5">
        {lignes.map((ligne) => (
          <li key={ligne.name} className="flex items-center gap-3">
            {/* Au classement final, la medaille remplace le numero : c'est le
                meme resultat que voit la salle, et le jury doit reconnaitre
                son ecran dans le sien. Le rang est partage a egalite, comme
                partout ailleurs. */}
            {final && ligne.rank <= 3 ? (
              <Medaille rang={ligne.rank} taille={34} />
            ) : (
              <span
                className="chiffres flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold leading-none text-white"
                style={{ background: ligne.color }}
              >
                {ligne.rank}
              </span>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="flex min-w-0 items-baseline gap-1.5">
                  <span className="truncate text-sm font-semibold text-dark">
                    {ligne.name}
                  </span>
                  {/* Le jury doit lire la meme chose que la salle : deux
                      scores egaux a des rangs differents s'expliquent, ils ne
                      se devinent pas. */}
                  {ligne.separe ? (
                    <span className="shrink-0 rounded-full bg-accent/15 px-1.5 py-px text-[10px] font-bold text-accent-dk">
                      فُصل بجولة الحسم
                    </span>
                  ) : null}
                </p>
                <span className="chiffres text-base font-bold text-primary">
                  {ligne.points}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${(ligne.points / maximum) * 100}%`,
                    background: ligne.color,
                  }}
                />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Carte>
  );
}
