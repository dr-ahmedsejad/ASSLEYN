"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Trophy, Volume2, VolumeX, WifiOff } from "lucide-react";

import {
  LIBELLE_PLACE,
  Medaille,
  TEINTE_PLACE,
} from "@/components/Medaille";
import {
  arreter as arreterLesSons,
  definirMuet,
  estMuet,
  programmerTour,
  reveiller,
  sonPret,
} from "@/lib/sons";
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
   * Le son sur cet ecran.
   *
   * `muet` est le choix de l'appareil, relu dans un effet : le serveur ne le
   * connait pas, et lire le stockage pendant le rendu ferait diverger le HTML
   * envoye de celui que le navigateur reconstruit.
   *
   * `autorise` est autre chose — c'est le navigateur qui decide. Cet ecran est
   * ouvert puis laisse seul : personne ne le touche, et sans geste le son
   * reste bloque. Il faut donc le demander, une fois, explicitement.
   */
  const [muet, setMuet] = useState(false);
  const [autorise, setAutorise] = useState(false);
  useEffect(() => setMuet(estMuet("salle")), []);

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

  /**
   * Les sons du tour, poses d'avance sur l'horloge audio.
   *
   * Memes valeurs que le compte a rebours affiche — l'heure de depart et
   * l'ecart avec l'horloge du serveur — donc meme instant. Les deux ecrans
   * sonnent ensemble sans se parler : ils se calent sur la meme horloge.
   */
  useEffect(() => {
    if (!depart || muet) return;
    programmerTour({
      debut: depart,
      secondes: etat.turn_seconds,
      ecart: ecart.current ?? 0,
      ecran: "salle",
    });
    // Le contexte peut avoir ete cree sans etre actif. On le constate juste
    // apres, pour proposer le bouton d'activation plutot que rester muet
    // sans rien dire.
    const controle = setTimeout(() => setAutorise(sonPret()), 200);
    return () => {
      clearTimeout(controle);
      arreterLesSons();
    };
  }, [depart, muet, etat.turn_seconds]);

  /**
   * Le premier contact avec la page ouvre le son.
   *
   * Les navigateurs exigent un geste ; ils ne demandent pas lequel. Un doigt
   * pose n'importe ou sur l'ecran de la salle suffit donc, et c'est le geste
   * le plus probable — bien avant qu'on cherche un bouton.
   *
   * L'ecoute se retire d'elle-meme apres le premier evenement : elle n'a plus
   * rien a faire ensuite.
   */
  useEffect(() => {
    if (muet || autorise) return;
    const ouvrir = () => {
      void reveiller().then((pret) => {
        if (pret) setAutorise(true);
      });
    };
    const options = { once: true, passive: true } as const;
    window.addEventListener("pointerdown", ouvrir, options);
    window.addEventListener("keydown", ouvrir, options);
    return () => {
      window.removeEventListener("pointerdown", ouvrir);
      window.removeEventListener("keydown", ouvrir);
    };
  }, [muet, autorise]);

  async function activerLeSon() {
    if (!(await reveiller())) return;
    setAutorise(true);
    if (depart) {
      programmerTour({
        debut: depart,
        secondes: etat.turn_seconds,
        ecart: ecart.current ?? 0,
        ecran: "salle",
      });
    }
  }

  const restant = depart ? restantMesure : etat.turn_seconds;

  const termine = etat.state === "FINISHED";
  const classement = [...etat.classement].sort(
    (a, b) => a.rank - b.rank || a.display_order - b.display_order,
  );
  const maximum = Math.max(...classement.map((l) => l.points), 1);

  return (
    <main className="min-h-screen px-4 py-6 sm:px-8 sm:py-8">
      {/* ─── Titre ─────────────────────────────────────────────────
          Le sceau de l'institut ouvre l'ecran. Cette page est projetee
          devant des familles et parfois photographiee : ce qui en sort
          doit porter le nom de la maison, pas seulement celui du jeu. */}
      <header className="mb-6 text-center">
        {/* `img` plutot que `next/image` : la page doit s'afficher meme
            quand le reseau de la salle vacille, sans passer par le
            service d'optimisation. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo-institut-carre.png"
          alt="شعار معهد الأصلين"
          className="mx-auto h-16 w-16 object-contain sm:h-24 sm:w-24"
        />
        <p className="mt-2 text-[11px] font-bold tracking-[0.22em] text-accent-dk">
          معهد الأصلين
        </p>
        <h1 className="mt-1 text-2xl font-bold text-dark sm:text-4xl">
          {etat.name}
        </h1>
        {perdu ? (
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-gris/10 px-3 py-1 text-xs text-gris">
            <WifiOff size={12} />
            إعادة الاتصال…
          </p>
        ) : null}

        {/* Le reglage du son, sous le titre.
            Il etait en pied de page : sur un telephone il tombait sous la
            ligne de flottaison, donc invisible — et sans lui le navigateur
            reste muet. Tant que le son est bloque, c'est un bandeau qu'on ne
            peut pas manquer ; une fois ouvert, il redevient une pastille. */}
        <div className="mt-3 flex justify-center">
          {!muet && !autorise ? (
            <button
              type="button"
              onClick={() => void activerLeSon()}
              className="flex items-center gap-2 rounded-full border border-accent/60 bg-accent/15 px-5 py-2 text-sm font-bold text-accent-dk shadow-card transition-colors hover:bg-accent/25"
            >
              <Volume2 size={16} />
              اضغط لتفعيل صوت المؤقّت
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                const suivant = !muet;
                setMuet(suivant);
                definirMuet("salle", suivant);
              }}
              aria-pressed={muet}
              className="flex items-center gap-1.5 rounded-full border border-gray-200 bg-white/70 px-3 py-1 text-[11px] font-medium text-gris transition-colors hover:bg-white"
            >
              {muet ? <VolumeX size={12} /> : <Volume2 size={12} />}
              {muet ? "الصوت مكتوم" : "الصوت يعمل"}
            </button>
          )}
        </div>
      </header>

      {termine ? (
        <ListeTitrage lignes={classement} />
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
                {/* Une manche de departage ne fait pas partie du programme :
                    l'annoncer comme « الدور 7 من 6 » serait un contresens. */}
                <p className="chiffres text-xs text-white/75">
                  {tour.tiebreak_round > 0
                    ? `جولة الحسم ${tour.tiebreak_round}`
                    : `الجولة ${tour.round_number} · الدور ${tour.index + 1} من ${etat.tours_prevus}`}
                </p>
                <p className="mt-1 text-3xl font-bold text-white sm:text-5xl">
                  {tour.group_name}
                </p>

                {/* Qui repond. Une salle reconnait des noms avant de
                    reconnaitre une equipe, et les familles presentes
                    cherchent le leur. */}
                {tour.group_members.length > 0 ? (
                  <p className="mx-auto mt-1.5 max-w-2xl text-sm leading-relaxed text-white/85 sm:text-lg">
                    {tour.group_members.join(" · ")}
                  </p>
                ) : null}

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
      <p className="chiffres mt-8 text-center text-xs text-gris-lt sm:mt-5">
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
          className="flex items-center gap-4 rounded-2xl border border-gray-100 bg-white px-4 py-4 shadow-card"
          style={{ borderInlineStart: `5px solid ${ligne.color}` }}
        >
          <span className="chiffres w-8 shrink-0 text-center text-lg font-bold text-gris-lt">
            {ligne.rank}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-bold text-dark sm:text-2xl">
              {ligne.name}
            </p>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${(ligne.points / maximum) * 100}%`,
                  background: ligne.color,
                }}
              />
            </div>
          </div>
          <span
            className="chiffres text-3xl font-extrabold sm:text-5xl"
            style={{ color: ligne.color }}
          >
            {ligne.points}
          </span>
        </div>
      ))}
    </section>
  );
}

/**
 * Le classement final : une liste, une medaille par rang.
 *
 * Le podium a trois marches obligeait a choisir. A egalite de points il
 * fallait bien mettre quelqu'un au centre, et passe le troisieme rang
 * quelqu'un partait au tableau du dessous — deux decisions que le classement,
 * lui, ne prend pas.
 *
 * La liste ne choisit plus. Chaque groupe a sa ligne, son rang et sa
 * medaille ; deux ex aequo ont exactement la meme, a la meme hauteur. La forme
 * ne depend plus du nombre de groupes : trois ou douze, elle s'allonge.
 *
 * Ce qui reste de la ceremonie tient a trois choses : la premiere place est
 * surelevee et cerclee d'or, les confettis tombent sans fin, et la medaille
 * s'arrete au bronze — elle doit rester une chose qu'on gagne.
 */
function ListeTitrage({ lignes }: { lignes: EcranDirect["classement"] }) {
  /**
   * Personne ne se detache : tous les groupes ont le meme score.
   *
   * On ne cercle alors personne d'or — distinguer douze premiers ne distingue
   * plus rien — et on le dit en toutes lettres, sinon la salle cherche un
   * vainqueur dans une liste qui n'en designe aucun.
   */
  const egaliteGenerale =
    lignes.length > 1 && lignes.every((ligne) => ligne.rank === 1);

  //: Reference de la barre d'ecart : les points de la premiere place.
  const maximum = Math.max(...lignes.map((ligne) => ligne.points), 1);

  return (
    <section className="relative mx-auto max-w-4xl">
      <Confettis />

      <p className="mb-4 flex justify-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-accent/55 bg-accent/12 px-4 py-1.5 text-lg font-bold text-accent-dk sm:text-2xl">
          <Trophy size={22} />
          النتيجة النهائية
        </span>
      </p>

      {egaliteGenerale ? (
        <p className="mb-4 text-center text-sm text-gris sm:text-base">
          تعادل عام: كل المجموعات في المرتبة الأولى بالنقاط نفسها.
        </p>
      ) : null}

      <ol className="grid gap-2.5 sm:gap-3">
        {lignes.map((ligne) => (
          <LigneTitrage
            key={ligne.id}
            ligne={ligne}
            maximum={maximum}
            tete={ligne.rank === 1 && !egaliteGenerale}
          />
        ))}
      </ol>
    </section>
  );
}

/**
 * Une ligne du classement final.
 *
 * Le rail de couleur a gauche fait reconnaitre le groupe avant qu'on lise son
 * nom — de loin, c'est la couleur qui arrive en premier. La barre sous le nom
 * donne l'ecart avec la premiere place : elle dit si la course etait serree,
 * ce qu'une colonne de chiffres ne montre pas.
 */
function LigneTitrage({
  ligne,
  maximum,
  tete,
}: {
  ligne: EcranDirect["classement"][number];
  maximum: number;
  tete: boolean;
}) {
  const place = LIBELLE_PLACE[ligne.rank];
  const teinte = TEINTE_PLACE[ligne.rank];

  return (
    <li
      className={`carte-apparition relative grid grid-cols-[auto_1fr_auto] items-center gap-3 overflow-hidden rounded-2xl border bg-white ps-3 pe-2 shadow-card sm:gap-5 sm:ps-5 sm:pe-4 ${
        tete
          ? "border-accent/50 py-3.5 sm:py-5"
          : "border-gray-100 py-2.5 sm:py-3.5"
      }`}
      style={
        tete
          ? {
              // La couleur du groupe teinte le debut de la ligne, sans jamais
              // passer sous le nom : le texte reste sur du blanc.
              background: `linear-gradient(90deg, ${ligne.color}1f, #ffffff 62%)`,
              boxShadow:
                "0 0 0 1.5px rgba(229,192,24,.38), 0 10px 26px -14px rgba(4,54,31,.3)",
            }
          : undefined
      }
    >
      <span
        aria-hidden="true"
        className="absolute inset-y-0 start-0 w-1 sm:w-1.5"
        style={{ background: ligne.color }}
      />

      <span className="flex w-9 justify-center sm:w-14">
        {place ? (
          <Medaille
            rang={ligne.rank}
            taille={tete ? 46 : 38}
            className={
              tete ? "h-auto w-8 sm:w-[46px]" : "h-auto w-6 sm:w-[38px]"
            }
          />
        ) : (
          /* Au-dela du bronze, un chiffre. La medaille reste une chose qui se
             gagne, pas une decoration distribuee a toute la liste. */
          <span className="chiffres text-lg font-extrabold text-gris-lt sm:text-2xl">
            {ligne.rank}
          </span>
        )}
      </span>

      <div className="min-w-0">
        <p className="flex min-w-0 items-baseline gap-2">
          <span
            className={`truncate font-bold text-dark ${
              tete ? "text-base sm:text-3xl" : "text-sm sm:text-2xl"
            }`}
          >
            {ligne.name}
          </span>

          {/* Le libelle de la place accompagne le nom sur la meme ligne : en
              dessous, il decalait la barre d'ecart et allongeait la ligne
              sans rien dire de plus.

              Absent sur telephone : la medaille y porte deja son chiffre et
              son metal, et la place volee au nom compte davantage. */}
          {place ? (
            <span
              className="hidden shrink-0 rounded-full px-2 py-0.5 text-xs font-bold sm:inline-block"
              style={{ background: teinte.fond, color: teinte.texte }}
            >
              {place}
            </span>
          ) : null}
        </p>

        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-gray-100 sm:h-1.5">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${(ligne.points / maximum) * 100}%`,
              background: ligne.color,
            }}
          />
        </div>
      </div>

      <div className="min-w-[2.75rem] text-center sm:min-w-[4rem]">
        <p
          className={`chiffres font-extrabold leading-none ${
            tete ? "text-2xl sm:text-5xl" : "text-xl sm:text-4xl"
          }`}
          style={{ color: ligne.color }}
        >
          {ligne.points}
        </p>
        <p className="mt-0.5 text-[10px] text-gris sm:text-xs">نقطة</p>
      </div>
    </li>
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
  // Le blanc a disparu avec le fond sombre. Les teintes viennent du sceau
  // de l'institut : le bleu de l'arc et l'or du livre.
  const couleurs = ["#006633", "#E5C018", "#C82020", "#2159a8", "#e8a33d"];

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
