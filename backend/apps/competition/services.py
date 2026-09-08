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
    Turn,
    TurnAction,
    TurnOutcome,
)

#: Alphabet du code public : ni 0/O ni 1/l/I. Ce code se recopie parfois depuis
#: une projection, a l'autre bout d'une salle.
ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

#: Tolerance sur une heure annoncee par un navigateur en avance sur le serveur.
DERIVE_TOLEREE = timedelta(seconds=5)

#: Jolees preparees d'avance pour une ندوة شعرية.
#:
#: Cette seance n'a pas de fin ecrite : elle tourne jusqu'a ce que le jury
#: l'arrete. On ne peut donc pas creer « tous » les tours — mais on peut en
#: creer largement assez pour que le jury n'attende jamais le reseau, et
#: recharger la reserve des qu'elle s'epuise. Vingt-cinq jolees, c'est plus
#: qu'une soiree n'en contient, et ce sont des lignes vides qui ne couteront
#: rien : celles qui n'auront pas servi disparaissent a la cloture.
JOLEES_DAVANCE = 25


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
        if len(questions) < len(groupes):
            raise CompetitionInvalide(
                "عدد الأسئلة لا يكفي لجولة واحدة كاملة."
            )
        total = (len(questions) // len(groupes)) * len(groupes)
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

    if not competition_a_des_tours_restants(tour.competition):
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
    Classement : un point par tour correct, ex aequo a rang partage.

    Meme convention que les resultats de l'institut — deux groupes a egalite
    partagent le rang, et le suivant n'est pas supprime.
    """
    lignes = []
    for groupe in competition.groups.all():
        tours = groupe.turns.all()
        lignes.append(
            {
                "id": groupe.id,
                "name": groupe.name,
                "color": groupe.color,
                "display_order": groupe.display_order,
                "points": sum(1 for t in tours if t.outcome == TurnOutcome.CORRECT),
                "joues": sum(1 for t in tours if t.tranche),
                "restants": sum(1 for t in tours if not t.tranche),
            }
        )

    lignes.sort(key=lambda ligne: (-ligne["points"], ligne["display_order"]))
    rang, precedent = 0, None
    for ligne in lignes:
        if ligne["points"] != precedent:
            rang += 1
            precedent = ligne["points"]
        ligne["rank"] = rang
    return lignes


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
