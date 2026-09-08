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
    <main className="min-h-screen px-4 py-6 sm:px-8 sm:py-8">
      {/* ─── Titre ─────────────────────────────────────────────── */}
      <header className="mb-8 text-center sm:mb-6">
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

      {/* Une ندوة شعرية n'a pas de dernier tour : la salle voit ce qui a ete
          joue, pas une fraction dont le denominateur n'existe pas. */}
      <p className="chiffres mt-8 text-center text-xs text-white/40 sm:mt-5">
        {etat.tours_prevus === null
          ? etat.tours_joues
          : `${etat.tours_joues} / ${etat.tours_prevus}`}
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
 * Le classement final : un podium a trois marches, puis un tableau.
 *
 * Les groupes classes premier, deuxieme et troisieme montent sur la marche de
 * leur rang — a plusieurs si besoin — et les confettis tombent sans fin : la
 * fete dure autant que la projection. Les suivants passent au tableau, sans
 * faire semblant d'etre sur la scene.
 *
 * A egalite, deux groupes portent la meme medaille, le meme rang, et la meme
 * marche. Le classement est dense, comme partout ailleurs dans l'application.
 */

/**
 * Hauteur des socles, du plus haut au plus bas.
 *
 * C'est le socle, et non la carte, qui porte desormais la marche. Une marche
 * peut accueillir plusieurs groupes ; sa hauteur ne doit donc pas dependre de
 * ce qu'on pose dessus.
 */
const SOCLES: Record<number, string> = {
  1: "h-16 sm:h-20",
  2: "h-11 sm:h-16",
  3: "h-7 sm:h-11",
};

/** Teinte du socle, accordee au metal de la marche. */
const TEINTES_SOCLE: Record<number, { fond: string; chiffre: string }> = {
  1: { fond: "rgba(229,192,24,.28)", chiffre: "rgba(240,203,46,.85)" },
  2: { fond: "rgba(194,204,214,.24)", chiffre: "rgba(215,222,230,.8)" },
  3: { fond: "rgba(207,147,81,.24)", chiffre: "rgba(227,171,114,.8)" },
};

function Podium({ lignes }: { lignes: EcranDirect["classement"] }) {
  /**
   * Trois marches, et autant de groupes qu'il en faut sur chacune.
   *
   * On avait d'abord tenu a trois cartes exactement, quitte a renvoyer au
   * tableau un groupe pourtant classe troisieme. Une place du podium qui
   * n'apparait pas sur le podium se defend mal devant la salle : le rang est
   * dense, deux groupes a egalite ont vraiment le meme rang, et rien ne
   * justifie d'en descendre un plutot que l'autre.
   *
   * Le podium accueille donc tout le monde jusqu'au rang trois. Ce qui est
   * fixe, ce n'est plus le nombre de cartes mais le nombre de marches : les
   * ex aequo se serrent sur la leur, et la hauteur continue de dire le rang.
   */
  const surPodium = lignes.filter((ligne) => ligne.rank <= 3);
  const suivants = lignes.filter((ligne) => ligne.rank > 3);

  /**
   * Les marches, de droite a gauche : la deuxieme, la premiere, la troisieme.
   *
   * Une marche vide n'existe pas — a trois groupes tous premiers, il n'y a
   * qu'une marche, en pleine largeur.
   */
  const marches = [2, 1, 3]
    .map((rang) => ({
      rang,
      groupes: surPodium.filter((ligne) => ligne.rank === rang),
    }))
    .filter((marche) => marche.groupes.length > 0);

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
        <div className="mb-5 sm:mb-3" />
      )}

      {/* Une colonne par marche, a toutes les tailles.
          Empiler sur telephone rendait la forme du podium — celle qui dit le
          resultat avant qu'on lise les chiffres. Ce qui change avec la
          largeur, c'est l'echelle, jamais la disposition : socle, medaille,
          nom et points retrecissent ensemble.

          Les colonnes sont alignees par le bas : les socles reposent tous sur
          le meme sol, et c'est leur hauteur qui fait la marche. Les cartes se
          posent dessus et montent — une marche chargee monte donc plus haut,
          comme un vrai podium ou trois personnes tiennent sur la meme
          plateforme. */}
      <div
        className={`grid items-end gap-1.5 sm:gap-4 ${
          marches.length === 3
            ? "grid-cols-3"
            : marches.length === 2
              ? "grid-cols-2"
              : "grid-cols-1"
        }`}
      >
        {marches.map((marche) => (
          <div
            key={marche.rang}
            className="flex flex-col justify-end gap-1.5 sm:gap-3"
          >
            {marche.groupes.map((ligne) => (
              <CarteMarche
                key={ligne.id}
                ligne={ligne}
                serree={marche.groupes.length > 1}
              />
            ))}
            <Socle rang={marche.rang} />
          </div>
        ))}
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
 * Le socle d'une marche : ce qui reste du podium quand on enleve les groupes.
 *
 * Il porte le chiffre de la marche, dans le metal de sa medaille. C'est lui
 * qui dit le rang quand une marche chargee monte plus haut que celle du
 * dessus — le chiffre et le metal ne mentent pas, la hauteur des cartes si.
 */
function Socle({ rang }: { rang: number }) {
  const teinte = TEINTES_SOCLE[rang] ?? TEINTES_SOCLE[3];
  return (
    <div
      className={`flex items-center justify-center rounded-t-xl sm:rounded-t-2xl ${
        SOCLES[rang] ?? SOCLES[3]
      }`}
      style={{ background: teinte.fond }}
      aria-hidden="true"
    >
      <span
        className="chiffres text-lg font-extrabold leading-none sm:text-4xl"
        style={{ color: teinte.chiffre }}
      >
        {rang}
      </span>
    </div>
  );
}

/**
 * La carte d'un groupe sur sa marche.
 *
 * `serree` s'applique des qu'une marche accueille plusieurs groupes : les
 * cartes s'empilent, et une colonne de deux cartes pleine taille depassait le
 * haut d'un telephone. On retrecit alors l'ensemble plutot que de rogner le
 * nom, qui est ce que la salle cherche des yeux.
 */
function CarteMarche({
  ligne,
  serree,
}: {
  ligne: EcranDirect["classement"][number];
  serree: boolean;
}) {
  const premier = ligne.rank === 1;
  const grand = premier && !serree;
  return (
    <div
      className={`carte-apparition relative overflow-hidden rounded-2xl px-1.5 text-center sm:rounded-3xl sm:px-5 ${
        serree ? "py-2 sm:py-3" : "py-4 sm:py-6"
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
          taille={grand ? 104 : 84}
          fondColore
          className={
            grand
              ? "h-auto w-[3.6rem] sm:w-[104px]"
              : serree
                ? "h-auto w-9 sm:w-[56px]"
                : "h-auto w-11 sm:w-[84px]"
          }
        />
      </div>

      {/* `text-balance` evite qu'un nom de trois mots laisse un mot seul sur
          la derniere ligne, dans une colonne aussi etroite. Aucune hauteur
          n'est reservee : les cartes d'une meme marche sont empilees, pas
          cote a cote, et rien n'oblige plus deux ex aequo a se repondre au
          pixel pres. */}
      <p
        className={`mt-1.5 font-bold leading-tight text-balance text-white sm:mt-2 ${
          grand ? "text-sm sm:text-3xl" : serree ? "text-xs sm:text-lg" : "text-xs sm:text-xl"
        }`}
      >
        {ligne.name}
      </p>

      <p
        className={`chiffres mt-0.5 font-extrabold leading-none text-white sm:mt-1 ${
          grand
            ? "text-3xl sm:text-6xl"
            : serree
              ? "text-2xl sm:text-4xl"
              : "text-2xl sm:text-5xl"
        }`}
      >
        {ligne.points}
      </p>
      <p className="mt-0.5 text-[10px] text-white/70 sm:text-xs">نقطة</p>
    </div>
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
