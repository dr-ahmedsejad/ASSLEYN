"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Trophy, WifiOff } from "lucide-react";

import { Medaille } from "@/components/Medaille";
import type { EcranDirect } from "@/lib/types";

/**
 * L'ecran de la salle.
 *
 * Projete, lu de loin, par des gens qui ne toucheront jamais l'application.
 * Deux exigences donc : de grands caracteres, et **jamais de page vide**.
 *
 * Le sondage remplace une connexion permanente a dessein. Sur un reseau qui
 * hoquette, une socket se coupe et ne revient pas toujours ; une requete
 * ratee, elle, laisse simplement le dernier etat a l'ecran. Devant une salle,
 * un score fige quelques secondes vaut infiniment mieux qu'un ecran blanc.
 *
 * Le compte a rebours tourne sur l'horloge locale, cadree sur celle du serveur
 * a chaque reponse recue. Il continue donc pendant les coupures, et se
 * recale des le retour.
 */
export function EcranSalle({
  code,
  initial,
}: {
  code: string;
  initial: EcranDirect;
}) {
  const [etat, setEtat] = useState<EcranDirect>(initial);
  const [perdu, setPerdu] = useState(false);
  const [restantMesure, setRestant] = useState(initial.turn_seconds);

  /**
   * Ecart avec l'horloge du serveur, recale a chaque reponse recue.
   *
   * Lu dans les effets seulement : le rendu doit rester une fonction de son
   * etat, sinon deux affichages du meme etat pourraient differer.
   */
  const ecart = useRef<number | null>(null);

  const rafraichir = useCallback(async () => {
    try {
      const reponse = await fetch(`/api/direct/${code}`, { cache: "no-store" });
      if (!reponse.ok) throw new Error(String(reponse.status));
      const frais = (await reponse.json()) as EcranDirect;
      ecart.current = new Date(frais.maintenant).getTime() - Date.now();

      setEtat(frais);
      setPerdu(false);
    } catch {
      // On garde ce qui est affiche. La salle ne doit pas voir la panne.
      setPerdu(true);
    }
  }, [code]);

  useEffect(() => {
    if (ecart.current === null) {
      ecart.current = new Date(initial.maintenant).getTime() - Date.now();
    }
    const sondage = setInterval(() => void rafraichir(), 2000);
    return () => clearInterval(sondage);
  }, [rafraichir, initial.maintenant]);

  const tour = etat.tour;
  const depart = tour?.started_at ?? null;

  // Le decompte tourne ici, et nulle part ailleurs : lire l'horloge pendant le
  // rendu rendrait l'affichage imprevisible.
  useEffect(() => {
    if (!depart) return;
    const battement = setInterval(() => {
      const ecoule =
        (Date.now() + (ecart.current ?? 0) - new Date(depart).getTime()) / 1000;
      setRestant(Math.max(etat.turn_seconds - Math.floor(ecoule), 0));
    }, 250);
    return () => clearInterval(battement);
  }, [depart, etat.turn_seconds]);

  const restant = depart ? restantMesure : etat.turn_seconds;

  const termine = etat.state === "FINISHED";
  const classement = [...etat.classement].sort(
    (a, b) => a.rank - b.rank || a.display_order - b.display_order,
  );
  const maximum = Math.max(...classement.map((l) => l.points), 1);

  return (
    <main className="min-h-screen px-4 py-6 sm:px-8 sm:py-10">
      {/* ─── Titre ─────────────────────────────────────────────── */}
      <header className="mb-8 text-center">
        <p className="text-xs font-semibold tracking-[0.22em] text-accent">
          معهد الأصلين
        </p>
        <h1 className="mt-1 text-3xl font-bold text-white sm:text-5xl">
          {etat.name}
        </h1>
        {perdu ? (
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs text-white/70">
            <WifiOff size={12} />
            إعادة الاتصال…
          </p>
        ) : null}
      </header>

      {termine ? (
        <Podium lignes={classement} />
      ) : (
        <>
          {tour ? (
            <section className="mx-auto mb-8 max-w-4xl">
              <div
                className="rounded-3xl p-6 text-center sm:p-10"
                style={{
                  background: `linear-gradient(160deg, ${tour.group_color}, ${tour.group_color}bb)`,
                }}
              >
                <p className="chiffres text-xs text-white/75">
                  الجولة {tour.round_number} · الدور {tour.index + 1} من{" "}
                  {etat.tours_prevus}
                </p>
                <p className="mt-1 text-3xl font-bold text-white sm:text-5xl">
                  {tour.group_name}
                </p>

                {tour.question_text ? (
                  <p className="mx-auto mt-6 max-w-3xl text-xl leading-relaxed text-white/95 sm:text-3xl">
                    {tour.question_text}
                  </p>
                ) : null}

                <p
                  className={`chiffres mt-6 text-7xl font-extrabold tabular-nums sm:text-8xl ${
                    tour.en_marche && restant <= 10
                      ? "text-yellow-200"
                      : "text-white"
                  }`}
                >
                  {tour.en_marche ? restant : etat.turn_seconds}
                </p>
                <p className="text-sm text-white/70">
                  {tour.en_marche
                    ? restant === 0
                      ? "انتهى الوقت"
                      : "ثانية"
                    : "بانتظار الانطلاق"}
                </p>
              </div>
            </section>
          ) : null}

          <Tableau lignes={classement} maximum={maximum} />
        </>
      )}

      <p className="chiffres mt-8 text-center text-xs text-white/40">
        {etat.tours_joues} / {etat.tours_prevus}
      </p>
    </main>
  );
}

function Tableau({
  lignes,
  maximum,
}: {
  lignes: EcranDirect["classement"];
  maximum: number;
}) {
  return (
    <section className="mx-auto grid max-w-5xl gap-3 sm:grid-cols-2">
      {lignes.map((ligne) => (
        <div
          key={ligne.id}
          className="flex items-center gap-4 rounded-2xl bg-white/5 px-4 py-4 backdrop-blur"
          style={{ borderInlineStart: `5px solid ${ligne.color}` }}
        >
          <span className="chiffres w-8 shrink-0 text-center text-lg font-bold text-white/50">
            {ligne.rank}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-bold text-white sm:text-2xl">
              {ligne.name}
            </p>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${(ligne.points / maximum) * 100}%`,
                  background: ligne.color,
                }}
              />
            </div>
          </div>
          <span className="chiffres text-3xl font-extrabold text-white sm:text-5xl">
            {ligne.points}
          </span>
        </div>
      ))}
    </section>
  );
}

/**
 * Le classement final : une ceremonie, pas un tableau.
 *
 * La forme dit le resultat avant que les chiffres ne soient lus — la premiere
 * place monte, les autres l'entourent, et chacune porte sa medaille. Les
 * confettis tombent sans fin : la fete dure autant que la projection.
 *
 * A egalite, deux groupes portent la meme medaille et le meme rang. Le
 * classement est dense, comme partout ailleurs dans l'application.
 */
function Podium({ lignes }: { lignes: EcranDirect["classement"] }) {
  const premiers = lignes.filter((l) => l.rank <= 3);
  const suivants = lignes.filter((l) => l.rank > 3);

  return (
    <section className="relative mx-auto max-w-5xl">
      <Confettis />

      <p className="mb-8 flex items-center justify-center gap-3 text-center text-2xl font-bold text-accent sm:text-3xl">
        <Trophy size={28} />
        النتيجة النهائية
      </p>

      <div className="grid gap-4 sm:grid-cols-3 sm:items-end">
        {premiers.map((ligne) => {
          const premier = ligne.rank === 1;
          return (
            <div
              key={ligne.id}
              className={`carte-apparition relative overflow-hidden rounded-3xl px-5 text-center ${
                premier ? "py-8 sm:order-2" : "py-6"
              } ${ligne.rank === 2 ? "sm:order-1" : ""} ${
                ligne.rank === 3 ? "sm:order-3" : ""
              }`}
              style={{
                background: `linear-gradient(160deg, ${ligne.color}, ${ligne.color}aa)`,
                boxShadow: premier
                  ? "0 0 0 2px rgba(229,192,24,.55), 0 24px 60px -20px rgba(0,0,0,.6)"
                  : "0 16px 40px -18px rgba(0,0,0,.5)",
              }}
            >
              <div className="pastille-pop flex justify-center">
                <Medaille
                  rang={ligne.rank}
                  taille={premier ? 104 : 84}
                  fondColore
                />
              </div>

              <p
                className={`mt-2 font-bold text-white ${
                  premier ? "text-2xl sm:text-3xl" : "text-xl"
                }`}
              >
                {ligne.name}
              </p>

              <p
                className={`chiffres mt-1 font-extrabold text-white ${
                  premier ? "text-6xl" : "text-5xl"
                }`}
              >
                {ligne.points}
              </p>
              <p className="text-xs text-white/70">نقطة</p>
            </div>
          );
        })}
      </div>

      {suivants.length > 0 ? (
        <div className="mt-6 grid gap-2 sm:grid-cols-2">
          {suivants.map((ligne) => (
            <div
              key={ligne.id}
              className="flex items-center justify-between gap-3 rounded-xl bg-white/5 px-4 py-3"
              style={{ borderInlineStart: `4px solid ${ligne.color}` }}
            >
              <span className="flex items-center gap-3">
                <span className="chiffres text-sm text-white/50">
                  {ligne.rank}
                </span>
                <span className="text-lg font-semibold text-white">
                  {ligne.name}
                </span>
              </span>
              <span className="chiffres text-2xl font-bold text-white">
                {ligne.points}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

/**
 * Confettis plein ecran.
 *
 * Ceux de la carte de resultat, dont la chute est ici doublee : une carte de
 * telephone fait cinq cents pixels, un videoprojecteur beaucoup plus. Ils
 * tournent sans fin — la ceremonie reste a l'ecran le temps qu'il faut — et
 * s'effacent pour qui a demande moins d'animations.
 */
function Confettis() {
  const couleurs = ["#006633", "#E5C018", "#C82020", "#008844", "#ffffff"];

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 overflow-hidden"
    >
      {Array.from({ length: 46 }, (_, i) => (
        <span
          key={i}
          className="confetti"
          style={
            {
              insetInlineStart: `${(i * 100) / 46 + (i % 3) * 0.7}%`,
              background: couleurs[i % couleurs.length],
              "--derive": `${((i % 7) - 3) * 26}px`,
              "--tour": `${360 + (i % 4) * 180}deg`,
              "--duree": `${3.4 + (i % 6) * 0.42}s`,
              "--attente": `${(i % 11) * 0.28}s`,
              "--chute": "110vh",
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
