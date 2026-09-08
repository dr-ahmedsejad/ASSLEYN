"""
Regles du concours, hors de toute vue.

Deux points meritent d'etre lus avant le reste.

**Le deroule est calcule d'avance.** Au demarrage, les tours sont crees d'un
coup : le tour d'indice i revient au groupe `i % nombre_de_groupes` et porte
la question d'indice i. Le jury peut alors travailler sans reseau, puisque
plus rien n'a besoin d'etre demande au serveur pour savoir qui passe ensuite.

Une مسابقة ثقافية s'arrete quand ses questions sont epuisees, et le deroule
est alors complet des le depart. Une ندوة شعرية n'a pas de fin ecrite : elle
tourne jusqu'a ce que le jury l'arrete. On ne peut donc pas tout creer — on
pose une reserve large, qu'on recharge des qu'elle s'epuise, et ce qui n'a pas
servi disparait a la cloture.

**L'heure vient du navigateur, bornee par le serveur.** Un geste peut arriver
avec cinq minutes de retard, apres une coupure. Prendre l'heure d'arrivee
transformerait ce retard en depassement de temps, et ferait perdre un point a
une equipe qui avait repondu. On accepte donc l'heure annoncee, mais on la
borne : jamais dans le futur, jamais avant le debut du tour.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.competition.models import (
    Competition,
    CompetitionState,
    Group,
    GroupMember,
    Turn,
    TurnAction,
    TurnOutcome,
)

#: Alphabet du code public : ni 0/O ni 1/l/I. Ce code se recopie parfois depuis
#: une projection, a l'autre bout d'une salle.
ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

#: Tolerance sur une heure annoncee par un navigateur en avance sur le serveur.
DERIVE_TOLEREE = timedelta(seconds=5)

#: Couleurs proposees aux groupes.
#:
#: Le vert de l'institut d'abord, puis des teintes qui s'en distinguent de
#: loin — c'est a la couleur qu'un groupe se reconnait sur les deux ecrans,
#: avant que son nom se lise. Au-dela de huit groupes, on recommence : deux
#: equipes de meme couleur valent mieux qu'une teinte indistincte.
COULEURS_GROUPES = (
    "#006633",
    "#C82020",
    "#1d4ed8",
    "#b8930f",
    "#7c3aed",
    "#0f766e",
    "#be185d",
    "#c2410c",
)


def couleur_pour(rang: int) -> str:
    """La couleur du groupe d'indice `rang`."""
    return COULEURS_GROUPES[rang % len(COULEURS_GROUPES)]


#: Jolees preparees d'avance pour une ندوة شعرية.
#:
#: Cette seance n'a pas de fin ecrite : elle tourne jusqu'a ce que le jury
#: l'arrete. On ne peut donc pas creer « tous » les tours — mais on peut en
#: creer largement assez pour que le jury n'attende jamais le reseau, et
#: recharger la reserve des qu'elle s'epuise. Vingt-cinq jolees, c'est plus
#: qu'une soiree n'en contient, et ce sont des lignes vides qui ne couteront
#: rien : celles qui n'auront pas servi disparaissent a la cloture.
JOLEES_DAVANCE = 25


@transaction.atomic
def importer_groupes(
    competition: Competition, couples: list[tuple[str, str]]
) -> tuple[int, int]:
    """
    Constitue les groupes et leurs listes a partir d'un classeur.

    Rend le compte des groupes crees et des participantes inscrites.

    Deux choix a lire avant de modifier :

    - un groupe deja present est complete, pas recree. On depose la liste
      d'une classe, puis celle d'une autre, sans repartir de zero ;
    - le nom est pris tel quel, sans etre confronte au fichier des
      etudiantes. Ces participantes ne se connectent pas et rien ne leur est
      rattache : une correspondance n'apporterait rien, et son absence
      passerait pour une anomalie alors qu'elle sera la regle.
    """
    groupes: dict[str, Group] = {
        groupe.name: groupe for groupe in competition.groups.all()
    }
    rang_groupe = len(groupes)

    crees = 0
    inscrites = 0

    for nom_groupe, nom_membre in couples:
        groupe = groupes.get(nom_groupe)
        if groupe is None:
            groupe = Group.objects.create(
                competition=competition,
                name=nom_groupe,
                color=couleur_pour(rang_groupe),
                display_order=rang_groupe,
            )
            groupes[nom_groupe] = groupe
            rang_groupe += 1
            crees += 1

        if not nom_membre:
            continue

        # Le meme nom depose deux fois reste une seule participante : un
        # classeur se redepose souvent, corrige d'une ligne.
        _, cree = GroupMember.objects.get_or_create(
            group=groupe,
            name=nom_membre,
            defaults={"display_order": groupe.members.count()},
        )
        if cree:
            inscrites += 1

    return crees, inscrites


class CompetitionInvalide(Exception):
    """La competition ne remplit pas les conditions pour l'operation demandee."""


def generer_code(longueur: int = 6) -> str:
    """Code public unique, tire au hasard."""
    while True:
        code = "".join(secrets.choice(ALPHABET_CODE) for _ in range(longueur))
        if not Competition.objects.filter(code=code).exists():
            return code


def borner(instant, tour: Turn, maintenant=None):
    """
    Ramene une heure annoncee par le navigateur dans le domaine du plausible.

    Elle ne peut pas etre dans le futur — au-dela d'une derive d'horloge de
    quelques secondes — ni preceder le debut du tour qu'elle concerne.
    """
    maintenant = maintenant or timezone.now()
    if instant is None:
        return maintenant
    if instant > maintenant + DERIVE_TOLEREE:
        return maintenant
    if tour.started_at is not None and instant < tour.started_at:
        return tour.started_at
    return instant


@transaction.atomic
def demarrer(competition: Competition) -> int:
    """
    Cree tous les tours et ouvre la competition.

    Renvoie le nombre de tours crees. Rejouer l'appel ne recree rien : une
    competition deja lancee garde son deroule.
    """
    if competition.state == CompetitionState.RUNNING:
        return competition.turns.count()
    if competition.state == CompetitionState.FINISHED:
        raise CompetitionInvalide("المسابقة منتهية.")

    groupes = list(competition.groups.all())
    if len(groupes) < 2:
        raise CompetitionInvalide("المسابقة تحتاج مجموعتين على الأقل.")

    if competition.avec_questions:
        questions = list(competition.questions.all())
        # Ce qu'on garde pour un eventuel departage : de quoi faire passer
        # chaque groupe une fois, et pas davantage.
        gardees = competition.questions_reservees
        total = (max(len(questions) - gardees, 0) // len(groupes)) * len(groupes)
        if total < len(groupes):
            raise CompetitionInvalide(
                "عدد الأسئلة لا يكفي لجولة واحدة كاملة."
                if not gardees
                else "بعد حجز أسئلة الحسم لا تبقى أسئلة تكفي لجولة كاملة."
            )
    else:
        # ندوة شعرية : elle n'a pas de fin ecrite d'avance. On pose une
        # reserve de جولات, qui se rechargera d'elle-meme.
        questions = []
        total = JOLEES_DAVANCE * len(groupes)

    Turn.objects.bulk_create(
        [
            Turn(
                competition=competition,
                index=i,
                round_number=i // len(groupes) + 1,
                group=groupes[i % len(groupes)],
                question=questions[i] if questions else None,
            )
            for i in range(total)
        ]
    )

    competition.state = CompetitionState.RUNNING
    competition.started_at = timezone.now()
    competition.save(update_fields=["state", "started_at"])
    return total


@transaction.atomic
def lancer_tour(tour: Turn, *, client_uuid, demarre_a=None) -> Turn:
    """
    Met le chronometre en marche.

    Rejouer le geste ne redemarre pas le compte a rebours : le premier depart
    fait foi. C'est ce qui permet a la tablette de renvoyer sa file d'attente
    sans crainte apres une coupure.
    """
    if TurnAction.objects.filter(client_uuid=client_uuid).exists():
        return tour
    if tour.started_at is not None:
        TurnAction.objects.create(
            client_uuid=client_uuid, turn=tour, kind=TurnAction.Kind.START
        )
        return tour

    maintenant = timezone.now()
    instant = demarre_a or maintenant
    if instant > maintenant + DERIVE_TOLEREE:
        instant = maintenant

    tour.started_at = instant
    tour.save(update_fields=["started_at"])
    TurnAction.objects.create(
        client_uuid=client_uuid, turn=tour, kind=TurnAction.Kind.START
    )
    return tour


@transaction.atomic
def trancher(
    tour: Turn,
    *,
    outcome: str,
    client_uuid,
    par,
    decide_a=None,
    note: str = "",
) -> Turn:
    """
    Enregistre la decision du jury.

    Le depassement de temps n'est pas declare par le navigateur mais **calcule
    ici**, a partir des deux heures conservees. Un point accorde hors delai
    reste un point accorde : il compte, et il se voit.
    """
    if TurnAction.objects.filter(client_uuid=client_uuid).exists():
        return tour
    if tour.tranche:
        TurnAction.objects.create(
            client_uuid=client_uuid, turn=tour, kind=TurnAction.Kind.DECIDE
        )
        return tour

    instant = borner(decide_a, tour)
    limite = (
        tour.started_at + timedelta(seconds=tour.competition.turn_seconds)
        if tour.started_at
        else None
    )

    tour.outcome = outcome
    tour.decided_at = instant
    tour.decided_by = par
    tour.note = note[:255]
    tour.awarded_late = bool(
        outcome == TurnOutcome.CORRECT and limite is not None and instant > limite
    )
    tour.save(
        update_fields=["outcome", "decided_at", "decided_by", "note", "awarded_late"]
    )
    TurnAction.objects.create(
        client_uuid=client_uuid, turn=tour, kind=TurnAction.Kind.DECIDE
    )

    if tour.tiebreak_round > 0:
        # Une manche de departage se ferme sur elle-meme. Recharger une ندوة
        # ici lui ajouterait vingt-cinq جولات au moment du classement final.
        if not tour.competition.turns.filter(
            outcome=TurnOutcome.PENDING, tiebreak_round__gt=0
        ).exists():
            cloturer(tour.competition)
    elif not competition_a_des_tours_restants(tour.competition):
        if tour.competition.avec_questions:
            # Les questions sont epuisees : la مسابقة ثقافية est finie.
            cloturer(tour.competition)
        else:
            recharger(tour.competition)
    return tour


def competition_a_des_tours_restants(competition: Competition) -> bool:
    return competition.turns.filter(outcome=TurnOutcome.PENDING).exists()


@transaction.atomic
def recharger(competition: Competition) -> int:
    """
    Remet des jolees d'avance dans une ندوة شعرية.

    Rien ici ne decide de la fin : seul le jury l'arrete. Tant qu'il ne l'a pas
    fait, il doit toujours avoir un tour a lancer, y compris s'il depasse la
    reserve posee au demarrage.
    """
    groupes = list(competition.groups.all())
    if not groupes:
        return 0

    depart = competition.turns.count()
    Turn.objects.bulk_create(
        [
            Turn(
                competition=competition,
                index=depart + i,
                round_number=(depart + i) // len(groupes) + 1,
                group=groupes[(depart + i) % len(groupes)],
                question=None,
            )
            for i in range(JOLEES_DAVANCE * len(groupes))
        ]
    )
    return JOLEES_DAVANCE * len(groupes)


@transaction.atomic
def cloturer(competition: Competition) -> Competition:
    """
    Ferme la session. Le classement devient definitif.

    Les tours prepares d'avance qui n'ont jamais ete lances disparaissent : ce
    sont des lignes que personne n'a jouees, et les laisser ferait croire a une
    seance interrompue alors qu'elle s'est terminee quand le jury l'a voulu.
    Un tour lance mais non tranche reste, lui : il a eu lieu.
    """
    if competition.state != CompetitionState.FINISHED:
        competition.state = CompetitionState.FINISHED
        competition.finished_at = timezone.now()
        competition.save(update_fields=["state", "finished_at"])

    competition.turns.filter(
        outcome=TurnOutcome.PENDING, started_at__isnull=True
    ).delete()
    return competition


def classement(competition: Competition) -> list[dict]:
    """
    Classement : un point par tour ordinaire gagne, ex aequo a rang partage.

    Les tours de **barrage** ne rapportent aucun point. Ils servent uniquement
    a ordonner des groupes deja a egalite : un groupe a cinq points qui gagne
    le barrage reste a cinq points, il passe seulement devant celles qui en
    avaient cinq aussi. Sans cette separation, une manche de departage ferait
    depasser un groupe qu'on n'avait pas rattrape sur le terrain.

    Deux groupes partagent donc un rang lorsqu'ils ont **et** le meme nombre
    de points **et** le meme parcours de barrage — c'est-a-dire quand rien ne
    les a departages.
    """
    manches = (
        competition.turns.order_by("-tiebreak_round")
        .values_list("tiebreak_round", flat=True)
        .first()
        or 0
    )

    lignes = []
    for groupe in competition.groups.all():
        tours = list(groupe.turns.all())
        ordinaires = [tour for tour in tours if tour.tiebreak_round == 0]
        departage = [tour for tour in tours if tour.tiebreak_round > 0]

        # Le resultat manche par manche, et non leur somme. Une victoire a la
        # premiere manche vaut plus qu'une victoire a la seconde : la premiere
        # se gagne contre tout le monde, la seconde seulement contre ceux qui
        # avaient deja perdu. Les additionner remettrait a egalite un groupe
        # sorti en tete et un groupe repeche au tour suivant.
        victoires = [
            1
            if any(
                tour.tiebreak_round == manche and tour.outcome == TurnOutcome.CORRECT
                for tour in departage
            )
            else 0
            for manche in range(1, manches + 1)
        ]

        lignes.append(
            {
                "id": groupe.id,
                "name": groupe.name,
                "color": groupe.color,
                "display_order": groupe.display_order,
                "points": sum(
                    1 for t in ordinaires if t.outcome == TurnOutcome.CORRECT
                ),
                "joues": sum(1 for t in ordinaires if t.tranche),
                "restants": sum(1 for t in ordinaires if not t.tranche),
                "departage": victoires,
            }
        )

    lignes.sort(
        key=lambda ligne: (
            -ligne["points"],
            tuple(-victoire for victoire in ligne["departage"]),
            ligne["display_order"],
        )
    )
    rang, precedent = 0, None
    for ligne in lignes:
        marque = (ligne["points"], tuple(ligne["departage"]))
        if marque != precedent:
            rang += 1
            precedent = marque
        ligne["rank"] = rang

    # Deux lignes au meme score et a des rangs differents : sans un mot, cela
    # ressemble a une erreur de calcul. On marque les deux — celle qui a gagne
    # le departage comme celle qui l'a perdu, puisque c'est le meme fait qui
    # explique les deux places.
    for ligne in lignes:
        ligne["separe"] = any(
            autre is not ligne
            and autre["points"] == ligne["points"]
            and autre["rank"] != ligne["rank"]
            for autre in lignes
        )
    return lignes


def groupes_a_departager(competition: Competition) -> list[dict]:
    """
    Les groupes de la plus haute egalite non resolue, ou une liste vide.

    Une seule egalite a la fois, et la plus haute d'abord. Avec trois groupes
    au premier rang et deux au deuxieme, le barrage ne concerne que les trois
    premieres ; les deux autres deviennent quatriemes ex aequo, et le jury
    decide ensuite s'il veut les departager a leur tour — souvent, seul le
    podium l'interesse.
    """
    lignes = classement(competition)
    compte: dict[int, int] = {}
    for ligne in lignes:
        compte[ligne["rank"]] = compte.get(ligne["rank"], 0) + 1

    for ligne in lignes:  # deja tries du meilleur rang au dernier
        if compte[ligne["rank"]] > 1:
            return [autre for autre in lignes if autre["rank"] == ligne["rank"]]
    return []


def questions_de_reserve(competition: Competition) -> list:
    """
    Les enonces qu'aucun tour n'utilise.

    Ce sont ceux que le deroule laisse de cote pour que chaque groupe reponde
    au meme nombre de questions. Ils ne servaient a rien ; ils alimentent
    desormais les manches de departage — et chaque manche consomme les siens,
    donc la reserve fond a mesure.
    """
    utilisees = set(
        competition.turns.exclude(question=None).values_list("question_id", flat=True)
    )
    return [
        question
        for question in competition.questions.all()
        if question.id not in utilisees
    ]


@transaction.atomic
def lancer_barrage(competition: Competition) -> tuple[int, int]:
    """
    Ouvre une manche de departage entre les groupes a egalite.

    Rend le numero de la manche et le nombre de groupes concernes. La session
    repasse en cours : le jury joue ces tours comme les autres, avec les memes
    boutons, et la cloture revient d'elle-meme quand ils sont tous tranches.

    Le temps de reponse n'entre nulle part. C'est le jury qui tranche, comme
    pour tout le reste : sur un reseau qui hoquette, une heure enregistree dit
    surtout quand le doigt s'est pose.
    """
    # Un departage se joue sur un classement acquis. Tant qu'il reste des
    # tours ordinaires, tout le monde est a egalite a zero point : ouvrir une
    # manche a ce moment-la departagerait des groupes qui n'ont pas encore
    # joue.
    if competition.turns.filter(
        outcome=TurnOutcome.PENDING, tiebreak_round=0
    ).exists():
        raise CompetitionInvalide("المسابقة لم تنته بعد.")

    if competition.turns.filter(
        outcome=TurnOutcome.PENDING, tiebreak_round__gt=0
    ).exists():
        raise CompetitionInvalide("جولة الحسم جارية بالفعل.")

    egalite = groupes_a_departager(competition)
    if len(egalite) < 2:
        raise CompetitionInvalide("لا يوجد تعادل يحتاج الحسم.")

    groupes = {
        groupe.id: groupe
        for groupe in competition.groups.filter(
            id__in=[ligne["id"] for ligne in egalite]
        )
    }

    # Les enonces de reserve, quand il y en a assez pour tout le monde.
    #
    # La reserve vaut le reste de la division des questions par les groupes :
    # elle est donc, par construction, **toujours plus petite que le nombre de
    # groupes**. Elle suffit rarement a une manche complete.
    #
    # Plutot que de refuser le departage pour une raison arithmetique — au
    # moment ou toute la salle attend —, on retombe sur ce que fait une ندوة
    # شعرية : un tour sans enonce. Le jury pose sa question a voix haute, le
    # chronometre tourne, il tranche. C'est ainsi que se tient un barrage
    # partout ailleurs.
    #
    # Tout ou rien : donner un enonce a l'ecran a une moitie des groupes et
    # pas a l'autre serait la seule injustice possible ici.
    questions = []
    if competition.avec_questions:
        reserve = questions_de_reserve(competition)
        if len(reserve) >= len(egalite):
            questions = reserve[: len(egalite)]

    manche = (
        competition.turns.order_by("-tiebreak_round")
        .values_list("tiebreak_round", flat=True)
        .first()
        or 0
    ) + 1
    depart = (
        competition.turns.order_by("-index").values_list("index", flat=True).first()
        or 0
    ) + 1

    Turn.objects.bulk_create(
        [
            Turn(
                competition=competition,
                index=depart + i,
                round_number=manche,
                tiebreak_round=manche,
                group=groupes[ligne["id"]],
                question=questions[i] if questions else None,
            )
            for i, ligne in enumerate(egalite)
        ]
    )

    competition.state = CompetitionState.RUNNING
    competition.finished_at = None
    competition.save(update_fields=["state", "finished_at"])
    return manche, len(egalite)


def tour_courant(competition: Competition) -> Turn | None:
    """
    Le tour sur lequel se joue l'attention.

    Celui qui est en cours s'il a demarre, sinon le prochain a jouer. `None`
    quand tout est tranche.
    """
    return (
        competition.turns.filter(outcome=TurnOutcome.PENDING)
        .select_related("group", "question")
        .order_by("index")
        .first()
    )
