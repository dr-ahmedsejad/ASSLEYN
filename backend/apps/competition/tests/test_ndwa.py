"""
La ندوة شعرية : un concours sans enonces.

Ce qui la distingue tient en trois points, et chacun peut casser en silence.
Le deroule ne vient plus des questions mais d'un nombre de جولات ; les tours
n'ont pas d'enonce, la ou tout le code en supposait un ; et rien ne doit
pouvoir glisser une question dans une seance qui n'en comporte pas.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from apps.competition import services
from apps.competition.models import (
    Competition,
    CompetitionKind,
    CompetitionState,
    Group,
    TurnOutcome,
)

from .test_concours import animateur, api_jury  # noqa: F401  (fixtures)


def _ndwa(groupes: int = 4, jolees: int = 3, par=None) -> Competition:
    competition = Competition.objects.create(
        name="ندوة المعلقات",
        kind=CompetitionKind.POETIQUE,
        code=services.generer_code(),
        rounds=jolees,
        created_by=par,
    )
    for i in range(groupes):
        Group.objects.create(
            competition=competition, name=f"المجموعة {i + 1}", display_order=i
        )
    return competition


@pytest.mark.django_db
def test_le_deroule_vient_des_jolees_et_non_des_questions(animateur) -> None:
    """Sans enonces, c'est le nombre de جولات qui fixe la seance."""
    competition = _ndwa(groupes=4, jolees=3, par=animateur)

    total = services.demarrer(competition)

    assert total == 12
    assert competition.tours_prevus() == 12
    assert competition.questions.count() == 0


@pytest.mark.django_db
def test_les_tours_n_ont_pas_d_enonce(animateur) -> None:
    competition = _ndwa(groupes=3, jolees=2, par=animateur)
    services.demarrer(competition)

    assert competition.turns.filter(question__isnull=False).count() == 0


@pytest.mark.django_db
def test_les_groupes_passent_a_tour_de_role(animateur) -> None:
    """Le tour de parole tourne, comme dans une مسابقة ثقافية."""
    competition = _ndwa(groupes=3, jolees=2, par=animateur)
    services.demarrer(competition)

    ordre = [tour.group.display_order for tour in competition.turns.order_by("index")]

    assert ordre == [0, 1, 2, 0, 1, 2]


@pytest.mark.django_db
def test_une_ndwa_sans_assez_de_groupes_est_refusee(animateur) -> None:
    competition = _ndwa(groupes=1, par=animateur)

    with pytest.raises(services.CompetitionInvalide):
        services.demarrer(competition)


@pytest.mark.django_db
def test_les_questions_sont_refusees_sur_une_ndwa(api_jury, animateur) -> None:
    """
    Le refus est cote serveur, pas seulement dans l'interface.

    L'ecran de preparation ne propose pas de champ pour les enonces ; rien
    n'empeche pourtant d'appeler la route directement, et un enonce ajoute
    apres coup serait ignore par le deroule sans que personne le sache.
    """
    competition = _ndwa(par=animateur)

    reponse = api_jury.post(
        reverse("competition-ajouter-questions", args=[competition.id]),
        {"textes": ["بيت من المعلقات"]},
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.questions.count() == 0


@pytest.mark.django_db
def test_le_type_ne_change_plus_apres_le_depart(api_jury, animateur) -> None:
    """
    Les tours sont crees au demarrage ; changer le type ensuite ne les
    changerait pas, mais ferait mentir tout ce qui est affiche.
    """
    competition = _ndwa(par=animateur)
    services.demarrer(competition)

    reponse = api_jury.patch(
        reverse("competition-detail", args=[competition.id]),
        {"kind": CompetitionKind.CULTURELLE},
        format="json",
    )
    competition.refresh_from_db()

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.kind == CompetitionKind.POETIQUE


@pytest.mark.django_db
def test_l_ecran_public_n_annonce_aucun_enonce(api, animateur) -> None:
    competition = _ndwa(groupes=2, jolees=1, par=animateur)
    services.demarrer(competition)

    corps = api.get(reverse("ecran-public", args=[competition.code])).data

    assert corps["kind"] == CompetitionKind.POETIQUE
    assert corps["tour"]["question_text"] is None
    assert corps["tour"]["group_name"] == "المجموعة 1"


@pytest.mark.django_db
def test_la_participation_compte_un_point(animateur) -> None:
    """Le classement se calcule comme ailleurs : un tour retenu, un point."""
    competition = _ndwa(groupes=2, jolees=2, par=animateur)
    services.demarrer(competition)

    for tour in competition.turns.order_by("index"):
        services.lancer_tour(tour, client_uuid=uuid.uuid4())
        services.trancher(
            tour,
            outcome=(
                TurnOutcome.CORRECT
                if tour.group.display_order == 0
                else TurnOutcome.NO_ANSWER
            ),
            client_uuid=uuid.uuid4(),
            par=animateur,
        )

    competition.refresh_from_db()
    classement = services.classement(competition)

    assert competition.state == CompetitionState.FINISHED
    assert [(ligne["points"], ligne["rank"]) for ligne in classement] == [(2, 1), (0, 2)]
