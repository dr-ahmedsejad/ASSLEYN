"""
Le departage des groupes a egalite.

Une regle gouverne tout le reste : **un barrage ne rapporte aucun point**. Il
ordonne des groupes deja a egalite, sans jamais leur faire depasser quelqu'un
qu'ils n'avaient pas rattrape sur le terrain. Un groupe a cinq points qui
gagne son barrage reste a cinq points.

Le temps de reponse n'entre nulle part. C'est le jury qui tranche, comme pour
tout le reste : sur un reseau qui hoquette, une heure enregistree dit surtout
quand le doigt s'est pose.
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
    Question,
    Turn,
    TurnOutcome,
)

from .test_concours import animateur, api_jury  # noqa: F401  (fixtures)


def _concours(par, groupes: int, questions: int, kind=CompetitionKind.CULTURELLE):
    competition = Competition.objects.create(
        name="مسابقة القرآن",
        kind=kind,
        code=services.generer_code(),
        created_by=par,
    )
    for i in range(groupes):
        Group.objects.create(
            competition=competition,
            name=f"المجموعة {i + 1}",
            display_order=i,
            color=services.couleur_pour(i),
        )
    for i in range(questions):
        Question.objects.create(
            competition=competition, text=f"السؤال {i + 1}", display_order=i
        )
    return competition


def _jouer(competition, points: dict[int, int], par):
    """Joue tout le deroule ordinaire pour atteindre les scores voulus."""
    restants = dict(points)
    for tour in competition.turns.filter(tiebreak_round=0).order_by("index"):
        rang = tour.group.display_order
        juste = restants.get(rang, 0) > 0
        if juste:
            restants[rang] -= 1
        services.lancer_tour(tour, client_uuid=uuid.uuid4())
        services.trancher(
            tour,
            outcome=TurnOutcome.CORRECT if juste else TurnOutcome.NO_ANSWER,
            client_uuid=uuid.uuid4(),
            par=par,
        )
    competition.refresh_from_db()


def _trancher_barrage(competition, gagnantes: set[int], par):
    """Le jury tranche la manche en cours : `gagnantes` par display_order."""
    for tour in competition.turns.filter(
        tiebreak_round__gt=0, outcome=TurnOutcome.PENDING
    ).order_by("index"):
        services.lancer_tour(tour, client_uuid=uuid.uuid4())
        services.trancher(
            tour,
            outcome=(
                TurnOutcome.CORRECT
                if tour.group.display_order in gagnantes
                else TurnOutcome.NO_ANSWER
            ),
            client_uuid=uuid.uuid4(),
            par=par,
        )
    competition.refresh_from_db()


def _rangs(competition) -> list[tuple[int, int]]:
    """(display_order, rang) dans l'ordre du classement."""
    return [
        (
            next(
                g.display_order
                for g in competition.groups.all()
                if g.id == ligne["id"]
            ),
            ligne["rank"],
        )
        for ligne in services.classement(competition)
    ]


# --------------------------------------------------------------------------
# Qui est departage
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_la_plus_haute_egalite_seule_est_departagee(animateur) -> None:
    """
    Trois groupes premiers, deux deuxiemes : le barrage ne prend que les trois.

    Les deux autres deviennent quatriemes ex aequo — apres les trois qui
    viennent d'etre separees — et le jury relance s'il veut les departager a
    leur tour. Souvent, seul le podium l'interesse.
    """
    competition = _concours(animateur, groupes=5, questions=20)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3, 2: 3, 3: 2, 4: 2}, animateur)

    egalite = services.groupes_a_departager(competition)

    assert [ligne["display_order"] for ligne in egalite] == [0, 1, 2]
    assert all(ligne["rank"] == 1 for ligne in egalite)


@pytest.mark.django_db
def test_les_egalites_se_resolvent_de_haut_en_bas(animateur) -> None:
    """
    Trois groupes premiers et deux deuxiemes : la chaine complete.

    Le premier barrage separe une gagnante des trois — mais **les deux
    perdantes restent a egalite entre elles**. Ce sont elles, et non les
    deuxiemes, que la manche suivante concerne : on ne descend d'un rang que
    lorsque celui du dessus est entierement resolu.

    C'est ce qui permet au jury de s'arreter quand il veut. Le podium se
    forme en deux manches ; la quatrieme place, si elle l'interesse, en
    demande une troisieme.
    """
    competition = _concours(animateur, groupes=5, questions=20)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3, 2: 3, 3: 2, 4: 2}, animateur)

    # Manche 1 : les trois premieres. Seule 0 repond juste.
    assert [l["display_order"] for l in services.groupes_a_departager(competition)] == [
        0,
        1,
        2,
    ]
    services.lancer_barrage(competition)
    _trancher_barrage(competition, gagnantes={0}, par=animateur)
    assert dict(_rangs(competition)) == {0: 1, 1: 2, 2: 2, 3: 3, 4: 3}

    # Manche 2 : 1 et 2, toujours a egalite — pas encore les deuxiemes.
    assert [l["display_order"] for l in services.groupes_a_departager(competition)] == [
        1,
        2,
    ]
    services.lancer_barrage(competition)
    _trancher_barrage(competition, gagnantes={1}, par=animateur)
    assert dict(_rangs(competition)) == {0: 1, 1: 2, 2: 3, 3: 4, 4: 4}

    # Le podium est fait. La quatrieme place attend, si le jury la veut.
    assert [l["display_order"] for l in services.groupes_a_departager(competition)] == [
        3,
        4,
    ]
    services.lancer_barrage(competition)
    _trancher_barrage(competition, gagnantes={3}, par=animateur)
    assert dict(_rangs(competition)) == {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}


@pytest.mark.django_db
def test_sans_egalite_il_n_y_a_rien_a_departager(animateur) -> None:
    competition = _concours(animateur, groupes=3, questions=12)
    services.demarrer(competition)
    _jouer(competition, {0: 4, 1: 3, 2: 2}, animateur)

    assert services.groupes_a_departager(competition) == []
    with pytest.raises(services.CompetitionInvalide):
        services.lancer_barrage(competition)


# --------------------------------------------------------------------------
# Ce que le barrage change, et ce qu'il ne change pas
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_barrage_ordonne_sans_faire_depasser_personne(animateur) -> None:
    """
    La regle qui gouverne tout : aucun point n'est marque.

    Deux groupes a deux points se departagent ; le gagnant ne doit pas passer
    devant celui qui en avait trois. Le barrage separe des egaux, il ne
    rattrape pas un retard.
    """
    competition = _concours(animateur, groupes=3, questions=12)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 2, 2: 2}, animateur)

    services.lancer_barrage(competition)
    _trancher_barrage(competition, gagnantes={1}, par=animateur)
    classement = services.classement(competition)

    assert dict(_rangs(competition)) == {0: 1, 1: 2, 2: 3}
    # Le gagnant du barrage garde ses deux points : rien ne s'ajoute.
    assert [ligne["points"] for ligne in classement] == [3, 2, 2]


@pytest.mark.django_db
def test_une_manche_indecise_en_appelle_une_autre(animateur) -> None:
    """Toutes justes, ou toutes fausses : personne n'est separe."""
    competition = _concours(animateur, groupes=2, questions=10)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3}, animateur)

    services.lancer_barrage(competition)
    _trancher_barrage(competition, gagnantes={0, 1}, par=animateur)

    assert dict(_rangs(competition)) == {0: 1, 1: 1}
    assert len(services.groupes_a_departager(competition)) == 2

    manche, groupes = services.lancer_barrage(competition)
    _trancher_barrage(competition, gagnantes={1}, par=animateur)

    assert (manche, groupes) == (2, 2)
    assert dict(_rangs(competition)) == {0: 2, 1: 1}


@pytest.mark.django_db
def test_la_manche_puise_dans_la_reserve_quand_elle_suffit(animateur) -> None:
    """
    Ces enonces ne servaient a rien.

    Le deroule en laisse de cote pour que chaque groupe reponde au meme nombre
    de questions. Quand il y en a assez pour toute la manche, le departage les
    utilise et les consomme.
    """
    competition = _concours(animateur, groupes=2, questions=7)  # 6 joues, 1 en reserve
    Question.objects.create(
        competition=competition, text="السؤال 8", display_order=7
    )
    services.demarrer(competition)
    # On ecourte le deroule de deux tours pour liberer deux enonces : c'est le
    # seul moyen d'obtenir une reserve aussi grande que le nombre de groupes,
    # puisque le calcul normal la limite au reste de la division.
    Turn.objects.filter(
        id__in=list(
            competition.turns.order_by("-index").values_list("id", flat=True)[:2]
        )
    ).delete()
    _jouer(competition, {0: 3, 1: 3}, animateur)

    assert len(services.questions_de_reserve(competition)) == 2
    services.lancer_barrage(competition)

    assert len(services.questions_de_reserve(competition)) == 0
    enonces = [
        tour.question.text
        for tour in competition.turns.filter(tiebreak_round=1).order_by("index")
    ]
    assert enonces == ["السؤال 7", "السؤال 8"]


@pytest.mark.django_db
def test_une_reserve_trop_maigre_donne_une_manche_sans_enonces(animateur) -> None:
    """
    Le cas ordinaire, et non l'exception.

    La reserve vaut le reste de la division des questions par les groupes :
    elle est donc toujours plus petite que le nombre de groupes, et ne suffit
    presque jamais. Refuser le departage pour cette raison arithmetique — au
    moment ou toute la salle attend — serait absurde. Les tours partent sans
    enonce, et le jury pose sa question a voix haute.
    """
    competition = _concours(animateur, groupes=3, questions=11)  # 2 en reserve
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3, 2: 3}, animateur)

    manche, groupes = services.lancer_barrage(competition)
    tours = competition.turns.filter(tiebreak_round=1)

    assert (manche, groupes) == (1, 3)
    assert tours.count() == 3
    assert tours.filter(question__isnull=False).count() == 0
    # La reserve n'a pas ete entamee : tout ou rien.
    assert len(services.questions_de_reserve(competition)) == 2


@pytest.mark.django_db
def test_le_barrage_ne_compte_pas_dans_les_tours_annonces(api, animateur) -> None:
    """La salle voit le programme, pas les manches qui s'y ajoutent."""
    competition = _concours(animateur, groupes=2, questions=6)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3}, animateur)
    services.lancer_barrage(competition)

    corps = api.get(reverse("ecran-public", args=[competition.code])).data

    assert corps["tours_prevus"] == 6
    assert corps["tours_joues"] == 6
    assert corps["tour"]["tiebreak_round"] == 1


# --------------------------------------------------------------------------
# L'etat de la session
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_la_session_rouvre_puis_se_referme_seule(animateur) -> None:
    competition = _concours(animateur, groupes=2, questions=6)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3}, animateur)
    assert competition.state == CompetitionState.FINISHED

    services.lancer_barrage(competition)
    competition.refresh_from_db()
    assert competition.state == CompetitionState.RUNNING

    _trancher_barrage(competition, gagnantes={0}, par=animateur)
    assert competition.state == CompetitionState.FINISHED


@pytest.mark.django_db
def test_une_ndwa_se_departage_sans_enonces(animateur) -> None:
    """Sans questions, un barrage ne coute que des tours."""
    competition = _concours(
        animateur, groupes=2, questions=0, kind=CompetitionKind.POETIQUE
    )
    services.demarrer(competition)
    for tour in competition.turns.order_by("index")[:4]:
        services.lancer_tour(tour, client_uuid=uuid.uuid4())
        services.trancher(
            tour,
            outcome=TurnOutcome.CORRECT,
            client_uuid=uuid.uuid4(),
            par=animateur,
        )
    services.cloturer(competition)
    competition.refresh_from_db()

    manche, groupes = services.lancer_barrage(competition)
    _trancher_barrage(competition, gagnantes={1}, par=animateur)

    assert (manche, groupes) == (1, 2)
    # La ندوة ne recharge pas ses vingt-cinq جولات au moment du classement.
    assert competition.state == CompetitionState.FINISHED
    assert dict(_rangs(competition)) == {0: 2, 1: 1}


@pytest.mark.django_db
def test_pas_de_departage_tant_que_la_competition_dure(animateur) -> None:
    """
    Au demarrage, tous les groupes sont a zero — donc tous « a egalite ».

    Ouvrir une manche a ce moment-la departagerait des equipes qui n'ont pas
    encore joue. Le refus porte sur les tours ordinaires restants, pas sur
    l'etat : c'est la seule mesure qui ne se laisse pas tromper par une
    session rouverte pour un departage precedent.
    """
    competition = _concours(animateur, groupes=3, questions=9)
    services.demarrer(competition)

    with pytest.raises(services.CompetitionInvalide) as erreur:
        services.lancer_barrage(competition)

    assert "تنته" in str(erreur.value)
    assert competition.turns.filter(tiebreak_round__gt=0).count() == 0


@pytest.mark.django_db
def test_une_manche_deja_ouverte_n_en_ouvre_pas_une_seconde(animateur) -> None:
    competition = _concours(animateur, groupes=2, questions=8)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3}, animateur)
    services.lancer_barrage(competition)

    with pytest.raises(services.CompetitionInvalide):
        services.lancer_barrage(competition)


# --------------------------------------------------------------------------
# Reserver de quoi departager
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_ajouter_des_questions_ne_reserve_rien(animateur) -> None:
    """
    Le piege, et la raison d'etre du reglage.

    La reserve vaut le reste de la division des questions par les groupes.
    Passer de dix a quinze questions pour cinq groupes ne met donc rien de
    cote : cela ajoute une جولة, et la reserve reste nulle. On ne peut pas
    obtenir une reserve en ajoutant des questions — il faut demander au
    deroule d'en garder.
    """
    competition = _concours(animateur, groupes=5, questions=15)
    services.demarrer(competition)

    assert competition.turns.count() == 15
    assert services.questions_de_reserve(competition) == []


@pytest.mark.django_db
def test_le_reglage_garde_un_enonce_par_groupe(animateur) -> None:
    competition = _concours(animateur, groupes=5, questions=15)
    competition.questions_reservees = 5
    competition.save(update_fields=["questions_reservees"])

    services.demarrer(competition)

    assert competition.turns.count() == 10  # deux جولات au lieu de trois
    assert len(services.questions_de_reserve(competition)) == 5


@pytest.mark.django_db
def test_la_reserve_peut_couvrir_plusieurs_manches(animateur) -> None:
    """
    Une manche ne suffit pas toujours a departager.

    Cinq groupes et vingt enonces reserves, ce sont quatre manches possibles :
    de quoi separer un peloton entier sans jamais avoir a poser de question a
    voix haute.
    """
    competition = _concours(animateur, groupes=5, questions=35)
    competition.questions_reservees = 20
    competition.save(update_fields=["questions_reservees"])

    services.demarrer(competition)

    assert competition.turns.count() == 15  # trois جولات
    assert len(services.questions_de_reserve(competition)) == 20


@pytest.mark.django_db
def test_la_manche_reservee_porte_ses_enonces(animateur) -> None:
    """C'est tout l'objet du reglage : un departage a l'ecran, pas a voix haute."""
    competition = _concours(animateur, groupes=3, questions=9)
    competition.questions_reservees = 3
    competition.save(update_fields=["questions_reservees"])
    services.demarrer(competition)
    _jouer(competition, {0: 2, 1: 2, 2: 2}, animateur)

    services.lancer_barrage(competition)
    manche = competition.turns.filter(tiebreak_round=1)

    assert manche.count() == 3
    assert manche.filter(question__isnull=False).count() == 3


@pytest.mark.django_db
def test_reserver_ne_doit_pas_vider_la_competition(animateur) -> None:
    """
    Cinq groupes, cinq questions : tout partirait en reserve.

    Le refus arrive au demarrage, pas en pleine seance, et il dit ce qui
    manque plutot que de laisser une competition sans aucun tour.
    """
    competition = _concours(animateur, groupes=5, questions=5)
    competition.questions_reservees = 5
    competition.save(update_fields=["questions_reservees"])

    with pytest.raises(services.CompetitionInvalide) as erreur:
        services.demarrer(competition)

    assert "الحسم" in str(erreur.value)


# --------------------------------------------------------------------------
# La route
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_la_route_ouvre_la_manche_et_la_console_l_apprend(api_jury, animateur) -> None:
    competition = _concours(animateur, groupes=2, questions=6)
    services.demarrer(competition)
    _jouer(competition, {0: 3, 1: 3}, animateur)

    avant = api_jury.get(
        reverse("competition-deroule", args=[competition.id])
    ).data["departage"]
    reponse = api_jury.post(
        reverse("competition-barrage", args=[competition.id]), format="json"
    )

    assert avant["groupes"] == ["المجموعة 1", "المجموعة 2"]
    # Six questions pour deux groupes : aucune reserve, donc a voix haute.
    assert avant["avec_enonces"] is False
    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data == {"manche": 1, "groupes": 2}
