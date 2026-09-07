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
 * Le classement final : une scene, puis un tableau.
 *
 * Trois cartes montent — la premiere place au centre, surelevee — et les
 * confettis tombent sans fin : la fete dure autant que la projection. Les
 * autres groupes suivent en tableau, lisiblement, sans faire semblant d'etre
 * sur la scene.
 *
 * A egalite, deux groupes portent la meme medaille et le meme rang. Le
 * classement est dense, comme partout ailleurs dans l'application.
 */
function Podium({ lignes }: { lignes: EcranDirect["classement"] }) {
  /**
   * Trois cartes, jamais plus — et le reste dans un tableau.
   *
   * On avait d'abord fait monter tous les groupes de rang inferieur ou egal a
   * trois. Le rang etant dense, ce nombre ne depend pas du nombre de groupes
   * mais du nombre de scores distincts : six groupes marquant 3, 3, 2, 2, 1, 1
   * montaient tous les six, et la forme qui devait dire le resultat avant
   * qu'on lise les chiffres ne disait plus rien.
   *
   * La regle est donc fixe : les trois premieres lignes du classement, quelles
   * que soient les egalites. La mise en scene garde une taille connue, le
   * tableau absorbe le reste, et rien ne deborde — ni sur telephone, ni a
   * douze groupes.
   */
  const premiers = lignes.slice(0, 3);
  const suivants = lignes.slice(3);

  /**
   * La forme de podium — une place surelevee entre deux autres — ne se tient
   * que si les trois cartes portent trois rangs differents. Deux premiers ex
   * aequo n'ont pas de deuxieme place a mettre a leur droite : les ordres
   * fixes se marcheraient dessus, et une carte doree se retrouverait plus bas
   * qu'une carte d'argent.
   *
   * Dans ce cas les trois cartes s'alignent a hauteur egale, dans l'ordre du
   * classement. Ce qui distingue la premiere place n'est plus la hauteur, mais
   * le cerne dore et la medaille : elle se distingue toujours.
   */
  const rangsDistincts = new Set(premiers.map((l) => l.rank)).size;
  const podiumClassique = premiers.length === 3 && rangsDistincts === 3;

  /**
   * Personne ne se detache : tous les groupes ont le meme score.
   *
   * Trois d'entre eux occupent quand meme la scene — il faut bien en placer
   * trois — mais l'ecran doit dire que ce choix ne recompense rien, sinon la
   * salle lit un vainqueur la ou il n'y en a pas.
   */
  const egaliteGenerale =
    lignes.length > 1 && lignes.every((ligne) => ligne.rank === 1);

  return (
    <section className="relative mx-auto max-w-5xl">
      <Confettis />

      <p className="mb-3 flex items-center justify-center gap-3 text-center text-2xl font-bold text-accent sm:text-3xl">
        <Trophy size={28} />
        النتيجة النهائية
      </p>

      {egaliteGenerale ? (
        <p className="mb-6 text-center text-base text-white/80 sm:text-lg">
          تعادل عام: كل المجموعات في المرتبة الأولى بالنقاط نفسها.
        </p>
      ) : (
        <div className="mb-5" />
      )}

      {/* Trois colonnes a toutes les tailles.
          Empiler sur telephone rendait la forme du podium — celle qui dit le
          resultat avant qu'on lise les chiffres. Ce qui change avec la
          largeur, c'est l'echelle, jamais la disposition : medaille, nom et
          points retrecissent ensemble. */}
      <div
        className={`grid gap-1.5 sm:gap-4 ${
          podiumClassique ? "items-end" : "items-stretch"
        } ${
          premiers.length === 3
            ? "grid-cols-3"
            : premiers.length === 2
              ? "grid-cols-2"
              : "grid-cols-1"
        }`}
      >
        {premiers.map((ligne) => {
          const premier = ligne.rank === 1;
          // La hauteur et l'ordre ne servent que le podium a trois cartes.
          const surelevation = podiumClassique
            ? `${premier ? "order-2 py-5 sm:py-8" : "py-3.5 sm:py-6"} ${
                ligne.rank === 2 ? "order-1" : ""
              } ${ligne.rank === 3 ? "order-3" : ""}`
            : "py-4 sm:py-6";
          return (
            <div
              key={ligne.id}
              className={`carte-apparition relative overflow-hidden rounded-2xl px-1.5 text-center sm:rounded-3xl sm:px-5 ${surelevation}`}
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
                  taille={premier && podiumClassique ? 104 : 84}
                  fondColore
                  className={
                    premier && podiumClassique
                      ? "h-auto w-[3.6rem] sm:w-[104px]"
                      : "h-auto w-11 sm:w-[84px]"
                  }
                />
              </div>

              {/* `text-balance` evite qu'un nom de trois mots laisse un mot
                  seul sur la derniere ligne, dans une colonne aussi etroite. */}
              <p
                className={`mt-1.5 font-bold leading-tight text-balance text-white sm:mt-2 ${
                  premier && podiumClassique
                    ? "text-sm sm:text-3xl"
                    : "text-xs sm:text-xl"
                }`}
              >
                {ligne.name}
              </p>

              <p
                className={`chiffres mt-0.5 font-extrabold leading-none text-white sm:mt-1 ${
                  premier && podiumClassique
                    ? "text-3xl sm:text-6xl"
                    : "text-2xl sm:text-5xl"
                }`}
              >
                {ligne.points}
              </p>
              <p className="mt-0.5 text-[10px] text-white/70 sm:text-xs">
                نقطة
              </p>
            </div>
          );
        })}
      </div>

      {/* Le reste du classement : un tableau, franchement.
          Ces groupes ne sont pas sur la scene ; leur donner des cartes en
          demi-teinte laissait croire a un second podium. Trois colonnes
          nommees se lisent de loin sans qu'on ait a deviner ce que chaque
          nombre represente. */}
      {suivants.length > 0 ? (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="text-sm text-white/55 sm:text-base">
                <th scope="col" className="w-16 py-2 pe-3 text-start font-semibold sm:w-24">
                  المرتبة
                </th>
                <th scope="col" className="py-2 text-start font-semibold">
                  المجموعة
                </th>
                <th scope="col" className="py-2 ps-3 text-end font-semibold">
                  النقاط
                </th>
              </tr>
            </thead>
            <tbody>
              {suivants.map((ligne) => (
                <tr key={ligne.id} className="border-t border-white/10">
                  <td className="py-3 pe-3 text-start">
                    {/* Une place du podium renvoyee au tableau garde sa
                        medaille : elle l'a gagnee, seule sa mise en scene a
                        change. Cinq groupes a 3, 3, 2, 2, 1 mettent un
                        deuxieme argent ici — il doit rester en argent. */}
                    {ligne.rank <= 3 ? (
                      <Medaille rang={ligne.rank} taille={30} fondColore />
                    ) : (
                      <span className="chiffres text-lg font-bold text-white/60 sm:text-2xl">
                        {ligne.rank}
                      </span>
                    )}
                  </td>
                  <td className="py-3">
                    <span className="flex min-w-0 items-center gap-3">
                      <span
                        className="h-5 w-1.5 shrink-0 rounded-full sm:h-7"
                        style={{ background: ligne.color }}
                      />
                      <span className="truncate text-lg font-semibold text-white sm:text-2xl">
                        {ligne.name}
                      </span>
                    </span>
                  </td>
                  <td className="py-3 ps-3 text-end">
                    <span className="chiffres text-xl font-bold text-white sm:text-3xl">
                      {ligne.points}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
