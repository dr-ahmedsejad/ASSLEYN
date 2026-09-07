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
  const surPodium = lignes.filter((l) => l.rank <= 3);

  /**
   * Au-dela de quatre cartes, le podium cesse d'etre un podium.
   *
   * Le nombre de places tenables ne depend pas du nombre de groupes mais du
   * nombre de scores distincts : le rang etant dense, tous ceux qui partagent
   * les trois meilleurs scores montent ensemble. Six groupes marquant
   * 3, 3, 2, 2, 1, 1 y montent tous les six — et la forme, qui devait dire le
   * resultat avant qu'on lise les chiffres, ne dit plus rien.
   *
   * Passe ce seuil, seule la premiere place reste en grand ; le reste redevient
   * un classement, ou les deuxieme et troisieme gardent leur medaille en
   * petit. On perd la mise en scene, on garde la lisibilite — c'est le bon
   * echange quand la mise en scene ne signifie plus rien.
   */
  const trop = surPodium.length > 4;
  const tete = trop ? lignes.filter((l) => l.rank === 1) : surPodium;

  /**
   * La premiere place elle-meme peut deborder : si tous les groupes finissent
   * a trois points, ils sont tous premiers. Reduire au rang 1 ne reduit alors
   * rien, et le retour a un podium de six cartes est complet.
   *
   * Il n'y a alors rien a mettre en scene — personne ne se detache. On le dit
   * en toutes lettres et on aligne tout le monde, plutot que de choisir
   * quatre gagnants parmi six a egalite parfaite.
   */
  const egaliteGenerale = tete.length > 4;
  const premiers = egaliteGenerale ? [] : tete;
  const suivants = lignes.filter((l) => !premiers.includes(l));

  /**
   * Le podium classique — une place surelevee entre deux autres — suppose
   * exactement trois cartes. Les ex aequo n'en donnent pas toujours trois :
   * deux groupes seulement, ou cinq groupes dont deux paires a egalite, en
   * produisent deux, quatre, cinq… Les ordres fixes se marcheraient alors
   * dessus et la grille deborderait sur une seconde ligne bancale.
   *
   * Hors de ce cas, les cartes s'alignent simplement dans l'ordre du
   * classement, a hauteur egale. La premiere place garde son cerne dore : ce
   * qui la distingue n'est plus la hauteur, mais elle se distingue toujours.
   */
  const podiumClassique = premiers.length === 3;

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
        className={
          premiers.length === 0
            ? "hidden"
            : podiumClassique
              ? "grid grid-cols-3 items-end gap-1.5 sm:gap-4"
              : "grid grid-cols-2 items-stretch gap-2 sm:grid-cols-3 sm:gap-4"
        }
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

      {suivants.length > 0 ? (
        <div
          className={`grid gap-2 sm:grid-cols-2 ${
            premiers.length === 0 ? "" : "mt-6"
          }`}
        >
          {suivants.map((ligne) => (
            <div
              key={ligne.id}
              className="flex items-center justify-between gap-3 rounded-xl bg-white/5 px-4 py-3"
              style={{ borderInlineStart: `4px solid ${ligne.color}` }}
            >
              <span className="flex min-w-0 items-center gap-3">
                {/* Une place du podium relegue a la liste garde sa medaille :
                    elle l'a gagnee, seule sa mise en scene a change. */}
                {ligne.rank <= 3 ? (
                  <Medaille rang={ligne.rank} taille={30} fondColore />
                ) : (
                  <span className="chiffres w-[30px] text-center text-sm text-white/50">
                    {ligne.rank}
                  </span>
                )}
                <span className="truncate text-lg font-semibold text-white">
                  {ligne.name}
                </span>
              </span>
              <span className="chiffres shrink-0 text-2xl font-bold text-white">
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
