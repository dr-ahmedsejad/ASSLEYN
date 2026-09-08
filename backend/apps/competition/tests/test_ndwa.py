"""
La ندوة شعرية : un concours sans enonces.

Ce qui la distingue tient en quatre points, et chacun peut casser en silence.
Elle n'a pas de fin ecrite d'avance — seul le jury l'arrete ; les tours n'ont
pas d'enonce, la ou tout le code en supposait un ; rien ne doit pouvoir
glisser une question dans une seance qui n'en comporte pas ; et ce qui a ete
prepare sans jamais servir ne doit pas figurer au compte rendu.
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

from .test_concours import (  # noqa: F401  (fixtures)
    animateur,
    api_admin,
    api_jury,
)


def _ndwa(groupes: int = 4, par=None) -> Competition:
    competition = Competition.objects.create(
        name="ندوة المعلقات",
        kind=CompetitionKind.POETIQUE,
        code=services.generer_code(),
        created_by=par,
    )
    for i in range(groupes):
        Group.objects.create(
            competition=competition, name=f"المجموعة {i + 1}", display_order=i
        )
    return competition


@pytest.mark.django_db
def test_la_seance_n_a_pas_de_fin_annoncee(animateur) -> None:
    """
    Elle tourne jusqu'a ce que le jury l'arrete.

    La reserve preparee n'est pas un programme : `tours_prevus` doit dire « on
    ne sait pas » plutot que d'annoncer son propre stock, sinon la salle lit un
    dixieme sur septante-cinq.
    """
    competition = _ndwa(groupes=4, par=animateur)

    total = services.demarrer(competition)

    assert competition.tours_prevus() == 0
    assert total == services.JOLEES_DAVANCE * 4


@pytest.mark.django_db
def test_les_tours_n_ont_pas_d_enonce(animateur) -> None:
    competition = _ndwa(groupes=3, par=animateur)
    services.demarrer(competition)

    assert competition.turns.filter(question__isnull=False).count() == 0


@pytest.mark.django_db
def test_les_groupes_passent_a_tour_de_role(animateur) -> None:
    """Le tour de parole tourne, comme dans une مسابقة ثقافية."""
    competition = _ndwa(groupes=3, par=animateur)
    services.demarrer(competition)

    ordre = [
        tour.group.display_order
        for tour in competition.turns.order_by("index")[:6]
    ]

    assert ordre == [0, 1, 2, 0, 1, 2]


@pytest.mark.django_db
def test_la_reserve_se_recharge_avant_de_s_epuiser(animateur) -> None:
    """
    Le jury ne doit jamais se retrouver sans tour a lancer.

    Une seance plus longue que la reserve posee au demarrage ne s'arrete pas
    d'elle-meme : c'est le seul point ou l'ecart avec la مسابقة ثقافية compte
    vraiment, puisque celle-ci se termine quand ses questions sont epuisees.
    """
    competition = _ndwa(groupes=2, par=animateur)
    services.demarrer(competition)
    depart = competition.turns.count()

    for tour in competition.turns.order_by("index"):
        services.lancer_tour(tour, client_uuid=uuid.uuid4())
        services.trancher(
            tour,
            outcome=TurnOutcome.CORRECT,
            client_uuid=uuid.uuid4(),
            par=animateur,
        )

    competition.refresh_from_db()

    assert competition.state == CompetitionState.RUNNING
    assert competition.turns.count() > depart
    assert services.tour_courant(competition) is not None


@pytest.mark.django_db
def test_une_ndwa_sans_assez_de_groupes_est_refusee(animateur) -> None:
    competition = _ndwa(groupes=1, par=animateur)

    with pytest.raises(services.CompetitionInvalide):
        services.demarrer(competition)


@pytest.mark.django_db
def test_les_questions_sont_refusees_sur_une_ndwa(api_admin, animateur) -> None:
    """
    Le refus est cote serveur, pas seulement dans l'interface.

    L'ecran de preparation ne propose pas de champ pour les enonces ; rien
    n'empeche pourtant d'appeler la route directement, et un enonce ajoute
    apres coup serait ignore par le deroule sans que personne le sache.
    """
    competition = _ndwa(par=animateur)

    reponse = api_admin.post(
        reverse("competition-ajouter-questions", args=[competition.id]),
        {"textes": ["بيت من المعلقات"]},
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.questions.count() == 0


@pytest.mark.django_db
def test_le_type_ne_change_plus_apres_le_depart(api_admin, animateur) -> None:
    """
    Les tours sont crees au demarrage ; changer le type ensuite ne les
    changerait pas, mais ferait mentir tout ce qui est affiche.
    """
    competition = _ndwa(par=animateur)
    services.demarrer(competition)

    reponse = api_admin.patch(
        reverse("competition-detail", args=[competition.id]),
        {"kind": CompetitionKind.CULTURELLE},
        format="json",
    )
    competition.refresh_from_db()

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.kind == CompetitionKind.POETIQUE


@pytest.mark.django_db
def test_l_ecran_public_n_annonce_ni_enonce_ni_dernier_tour(api, animateur) -> None:
    competition = _ndwa(groupes=2, par=animateur)
    services.demarrer(competition)

    corps = api.get(reverse("ecran-public", args=[competition.code])).data

    assert corps["kind"] == CompetitionKind.POETIQUE
    assert corps["tours_prevus"] is None
    assert corps["tour"]["question_text"] is None
    assert corps["tour"]["group_name"] == "المجموعة 1"


@pytest.mark.django_db
def test_le_jury_arrete_la_seance_et_le_prepare_disparait(api_jury, animateur) -> None:
    """
    La cloture est un geste, pas une consequence.

    Et elle nettoie : les tours prepares d'avance et jamais lances n'ont eu
    lieu pour personne. Les laisser ferait lire une seance interrompue la ou
    elle s'est terminee quand le jury l'a voulu.
    """
    competition = _ndwa(groupes=2, par=animateur)
    services.demarrer(competition)

    premier = competition.turns.order_by("index").first()
    services.lancer_tour(premier, client_uuid=uuid.uuid4())
    services.trancher(
        premier,
        outcome=TurnOutcome.CORRECT,
        client_uuid=uuid.uuid4(),
        par=animateur,
    )

    reponse = api_jury.post(
        reverse("competition-cloturer", args=[competition.id]), format="json"
    )
    competition.refresh_from_db()

    assert reponse.status_code == status.HTTP_200_OK
    assert competition.state == CompetitionState.FINISHED
    assert competition.turns.count() == 1


@pytest.mark.django_db
def test_la_participation_compte_un_point(animateur) -> None:
    """Le classement se calcule comme ailleurs : un tour retenu, un point."""
    competition = _ndwa(groupes=2, par=animateur)
    services.demarrer(competition)

    for tour in competition.turns.order_by("index")[:4]:
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
    services.cloturer(competition)

    competition.refresh_from_db()
    classement = services.classement(competition)

    assert competition.state == CompetitionState.FINISHED
    assert [(ligne["points"], ligne["rank"]) for ligne in classement] == [(2, 1), (0, 2)]
