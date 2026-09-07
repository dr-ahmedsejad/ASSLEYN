"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  CloudOff,
  Play,
  TimerOff,
  XCircle,
} from "lucide-react";

import { LienDirect } from "@/components/LienDirect";
import { Medaille } from "@/components/Medaille";
import { empiler, identifiant, vider } from "@/lib/file-hors-ligne";
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
  const [motif, setMotif] = useState("");
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

  const classement = useMemo(() => {
    const parGroupe = new Map<
      number,
      { name: string; color: string; points: number; ordre: number }
    >();
    tours.forEach((tour, position) => {
      const ligne = parGroupe.get(tour.group) ?? {
        name: tour.group_name,
        color: tour.group_color,
        points: 0,
        ordre: position,
      };
      if (tour.outcome === "CORRECT") ligne.points += 1;
      parGroupe.set(tour.group, ligne);
    });
    return [...parGroupe.values()].sort(
      (a, b) => b.points - a.points || a.ordre - b.ordre,
    );
  }, [tours]);

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

  // Tant que le tour n'a pas demarre, la duree pleine se deduit : inutile de
  // la poser dans l'etat, et l'y poser depuis un effet serait une mise a jour
  // synchrone de plus.
  const restant = depart ? restantMesure : competition.turn_seconds;
  const enMarche = Boolean(courant?.started_at);
  const expire = enMarche && restant === 0;
  const joues = tours.filter((t) => t.outcome !== "PENDING").length;

  function lancer() {
    if (!courant || courant.started_at) return;
    const depart = heureServeur().toISOString();
    empiler(`tours/${courant.id}/lancer`, {
      client_uuid: identifiant(),
      demarre_a: depart,
    });
    setTours((liste) =>
      liste.map((t) => (t.id === courant.id ? { ...t, started_at: depart } : t)),
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
        <Carte titre="انتهت المسابقة">
          <p className="text-sm text-gris">
            كل الأدوار حُسمت. النتيجة النهائية معروضة أدناه، وهي نفسها التي تظهر
            على شاشة القاعة.
          </p>
        </Carte>
        <Classement lignes={classement} final />
        <LienDirect code={competition.code} />
      </div>
    );
  }

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
          <p className="chiffres text-[11px] opacity-80">
            الجولة {courant.round_number} · الدور {courant.index + 1} من{" "}
            {tours.length}
          </p>
          <p className="mt-0.5 text-2xl font-bold leading-tight">
            {courant.group_name}
          </p>
        </div>

        <div className="flex flex-col items-center gap-5 p-5">
          <p className="text-center text-xl font-semibold leading-relaxed text-dark">
            {courant.question_text}
          </p>

          <Chronometre
            secondes={restant}
            fraction={fraction}
            enMarche={enMarche}
            couleur={courant.group_color}
          />

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
                {expire ? "إجابة صحيحة رغم انتهاء الوقت" : "إجابة صحيحة"}
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
        {joues} / {tours.length} دورا
      </p>

      <LienDirect code={competition.code} />
    </div>
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
          {!enMarche ? "بانتظار الانطلاق" : secondes === 0 ? "انتهى الوقت" : "ثانية"}
        </p>
      </div>
    </div>
  );
}

function Classement({
  lignes,
  final = false,
}: {
  lignes: { name: string; color: string; points: number }[];
  final?: boolean;
}) {
  const maximum = Math.max(...lignes.map((l) => l.points), 1);
  return (
    <Carte titre={final ? "النتيجة النهائية" : "النقاط"}>
      <ul className="space-y-2.5">
        {lignes.map((ligne, index) => (
          <li key={ligne.name} className="flex items-center gap-3">
            {/* Au classement final, la medaille remplace le numero : c'est le
                meme resultat que voit la salle, et le jury doit reconnaitre
                son ecran dans le sien. */}
            {final && index < 3 ? (
              <Medaille rang={index + 1} taille={34} />
            ) : (
              <span
                className="chiffres flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold leading-none text-white"
                style={{ background: ligne.color }}
              >
                {index + 1}
              </span>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-sm font-semibold text-dark">
                  {ligne.name}
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
