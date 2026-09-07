"""
Regles du concours.

Trois proprietes portent tout le reste : le deroule est equitable, les gestes
du jury supportent d'etre rejoues, et un point accorde hors delai reste
visible comme tel.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import Role, RolePermission, User
from apps.accounts.rbac import Permission
from apps.competition import services
from apps.competition.models import (
    Competition,
    CompetitionState,
    Group,
    Question,
    Turn,
    TurnOutcome,
)


@pytest.fixture
def animateur(db) -> User:
    """Un membre du jury : le droit se delegue, il n'est pas reserve a l'admin."""
    user = User.objects.create_user(
        username="jury", password="MotDePasse2026", full_name_ar="لجنة المسابقة"
    )
    user.role = Role.ASSISTANT
    user.save(update_fields=["role"])
    RolePermission.objects.get_or_create(
        role=Role.ASSISTANT, permission=Permission.COMPETITION_ANIMER
    )
    return user


@pytest.fixture
def api_jury(api, animateur):
    api.force_authenticate(animateur)
    return api


def _concours(groupes: int = 4, questions: int = 30, secondes: int = 30, par=None):
    competition = Competition.objects.create(
        name="مسابقة القرآن", code=services.generer_code(), turn_seconds=secondes,
        created_by=par,
    )
    for i in range(groupes):
        Group.objects.create(
            competition=competition, name=f"المجموعة {i + 1}", display_order=i
        )
    for i in range(questions):
        Question.objects.create(
            competition=competition, text=f"السؤال {i + 1}", display_order=i
        )
    return competition


# --------------------------------------------------------------------------
# Le deroule est equitable
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_deroule_se_limite_aux_jolees_completes(animateur) -> None:
    """
    Quatre groupes et trente questions donnent vingt-huit tours.

    Les deux questions en trop restent en reserve : sans cela, deux groupes
    auraient une occasion de plus que les autres et le classement se
    discuterait.
    """
    competition = _concours(groupes=4, questions=30, par=animateur)

    total = services.demarrer(competition)

    assert total == 28
    assert competition.turns.count() == 28
    par_groupe = {
        groupe.name: groupe.turns.count() for groupe in competition.groups.all()
    }
    assert set(par_groupe.values()) == {7}


@pytest.mark.django_db
def test_les_groupes_passent_a_tour_de_role(animateur) -> None:
    competition = _concours(groupes=3, questions=9, par=animateur)
    services.demarrer(competition)

    ordre = list(competition.turns.order_by("index").values_list("group__name", flat=True))

    assert ordre[:6] == [
        "المجموعة 1", "المجموعة 2", "المجموعة 3",
        "المجموعة 1", "المجموعة 2", "المجموعة 3",
    ]
    assert list(competition.turns.order_by("index").values_list("round_number", flat=True))[:6] == [
        1, 1, 1, 2, 2, 2,
    ]


@pytest.mark.django_db
def test_chaque_question_ne_sert_qu_une_fois(animateur) -> None:
    competition = _concours(groupes=4, questions=12, par=animateur)
    services.demarrer(competition)

    posees = list(competition.turns.values_list("question_id", flat=True))
    assert len(posees) == len(set(posees))


@pytest.mark.django_db
def test_un_concours_sans_assez_de_questions_est_refuse(animateur) -> None:
    competition = _concours(groupes=4, questions=3, par=animateur)

    with pytest.raises(services.CompetitionInvalide):
        services.demarrer(competition)


@pytest.mark.django_db
def test_relancer_le_demarrage_ne_recree_pas_le_deroule(animateur) -> None:
    competition = _concours(groupes=2, questions=6, par=animateur)
    services.demarrer(competition)

    services.demarrer(competition)

    assert competition.turns.count() == 6


# --------------------------------------------------------------------------
# Les gestes du jury supportent d'etre rejoues
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_relancer_un_tour_ne_redemarre_pas_le_chronometre(animateur) -> None:
    """
    La tablette peut renvoyer sa file d'attente deux fois apres une coupure.
    Si le depart se remettait a zero, l'equipe suivante gagnerait du temps.
    """
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()

    services.lancer_tour(tour, client_uuid=uuid.uuid4())
    depart = Turn.objects.get(pk=tour.pk).started_at

    services.lancer_tour(tour, client_uuid=uuid.uuid4())

    assert Turn.objects.get(pk=tour.pk).started_at == depart


@pytest.mark.django_db
def test_le_meme_geste_rejoue_ne_compte_qu_une_fois(animateur) -> None:
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()
    services.lancer_tour(tour, client_uuid=uuid.uuid4())

    identifiant = uuid.uuid4()
    services.trancher(
        tour, outcome=TurnOutcome.CORRECT, client_uuid=identifiant, par=animateur
    )
    services.trancher(
        tour, outcome=TurnOutcome.NO_ANSWER, client_uuid=identifiant, par=animateur
    )

    tour.refresh_from_db()
    assert tour.outcome == TurnOutcome.CORRECT
    assert services.classement(competition)[0]["points"] == 1


@pytest.mark.django_db
def test_un_tour_deja_tranche_ne_se_retranche_pas(animateur) -> None:
    """Deux identifiants differents, mais le premier verdict reste."""
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()
    services.lancer_tour(tour, client_uuid=uuid.uuid4())
    services.trancher(
        tour, outcome=TurnOutcome.CORRECT, client_uuid=uuid.uuid4(), par=animateur
    )

    services.trancher(
        tour, outcome=TurnOutcome.NO_ANSWER, client_uuid=uuid.uuid4(), par=animateur
    )

    tour.refresh_from_db()
    assert tour.outcome == TurnOutcome.CORRECT


@pytest.mark.django_db
def test_une_heure_annoncee_dans_le_futur_est_ramenee(animateur) -> None:
    """L'horloge d'une tablette peut etre fausse ; le classement, non."""
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()

    services.lancer_tour(
        tour,
        client_uuid=uuid.uuid4(),
        demarre_a=timezone.now() + timedelta(hours=3),
    )

    tour.refresh_from_db()
    assert tour.started_at <= timezone.now() + timedelta(seconds=5)


# --------------------------------------------------------------------------
# Le hors delai est une decision, pas une tolerance
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_un_point_accorde_dans_le_temps_n_est_pas_marque(animateur) -> None:
    competition = _concours(groupes=2, questions=4, secondes=30, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()
    depart = timezone.now() - timedelta(seconds=10)
    services.lancer_tour(tour, client_uuid=uuid.uuid4(), demarre_a=depart)

    services.trancher(
        tour, outcome=TurnOutcome.CORRECT, client_uuid=uuid.uuid4(), par=animateur
    )

    tour.refresh_from_db()
    assert tour.awarded_late is False


@pytest.mark.django_db
def test_un_point_accorde_hors_delai_compte_et_se_voit(animateur) -> None:
    """
    Le cas qui a motive la fonction : l'equipe avait repondu, le reseau a
    lache. Le point est du — et la decision doit rester lisible.
    """
    competition = _concours(groupes=2, questions=4, secondes=30, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()
    depart = timezone.now() - timedelta(seconds=45)
    services.lancer_tour(tour, client_uuid=uuid.uuid4(), demarre_a=depart)

    services.trancher(
        tour,
        outcome=TurnOutcome.CORRECT,
        client_uuid=uuid.uuid4(),
        par=animateur,
        note="أجابت في الوقت، انقطع الاتصال",
    )

    tour.refresh_from_db()
    assert tour.outcome == TurnOutcome.CORRECT
    assert tour.awarded_late is True
    assert tour.note == "أجابت في الوقت، انقطع الاتصال"
    assert tour.decided_by == animateur
    assert services.classement(competition)[0]["points"] == 1


@pytest.mark.django_db
def test_une_absence_de_reponse_n_est_jamais_hors_delai(animateur) -> None:
    """Le drapeau ne concerne qu'un point accorde : sinon il ne veut rien dire."""
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()
    services.lancer_tour(
        tour, client_uuid=uuid.uuid4(), demarre_a=timezone.now() - timedelta(minutes=2)
    )

    services.trancher(
        tour, outcome=TurnOutcome.NO_ANSWER, client_uuid=uuid.uuid4(), par=animateur
    )

    tour.refresh_from_db()
    assert tour.awarded_late is False


# --------------------------------------------------------------------------
# Classement et cloture
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_classement_partage_le_rang_a_egalite(animateur) -> None:
    competition = _concours(groupes=3, questions=6, par=animateur)
    services.demarrer(competition)
    # Groupes 1 et 2 marquent une fois, le groupe 3 rien.
    for tour in competition.turns.order_by("index")[:2]:
        services.lancer_tour(tour, client_uuid=uuid.uuid4())
        services.trancher(
            tour, outcome=TurnOutcome.CORRECT, client_uuid=uuid.uuid4(), par=animateur
        )

    lignes = services.classement(competition)

    assert [(x["name"], x["points"], x["rank"]) for x in lignes] == [
        ("المجموعة 1", 1, 1),
        ("المجموعة 2", 1, 1),
        ("المجموعة 3", 0, 2),
    ]


@pytest.mark.django_db
def test_le_dernier_tour_tranche_cloture_la_competition(animateur) -> None:
    competition = _concours(groupes=2, questions=2, par=animateur)
    services.demarrer(competition)

    for tour in competition.turns.all():
        services.lancer_tour(tour, client_uuid=uuid.uuid4())
        services.trancher(
            tour, outcome=TurnOutcome.NO_ANSWER, client_uuid=uuid.uuid4(), par=animateur
        )

    competition.refresh_from_db()
    assert competition.state == CompetitionState.FINISHED
    assert competition.finished_at is not None


# --------------------------------------------------------------------------
# L'ecran public
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_l_ecran_public_s_ouvre_sans_connexion(api, animateur) -> None:
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)

    reponse = api.get(reverse("ecran-public", args=[competition.code]))

    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data["name"] == "مسابقة القرآن"
    assert len(reponse.data["classement"]) == 2


@pytest.mark.django_db
def test_l_ecran_public_ne_montre_que_la_question_en_cours(api, animateur) -> None:
    """Les enonces suivants ne doivent jamais fuiter vers la salle."""
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)

    corps = api.get(reverse("ecran-public", args=[competition.code])).data

    assert corps["tour"]["question_text"] == "السؤال 1"
    rendu = str(corps)
    assert "السؤال 2" not in rendu
    assert "السؤال 3" not in rendu


@pytest.mark.django_db
def test_l_ecran_public_peut_taire_la_question(api, animateur) -> None:
    competition = _concours(groupes=2, questions=4, par=animateur)
    competition.show_question = False
    competition.save(update_fields=["show_question"])
    services.demarrer(competition)

    corps = api.get(reverse("ecran-public", args=[competition.code])).data

    assert corps["tour"]["question_text"] is None
    assert corps["tour"]["group_name"] == "المجموعة 1"


@pytest.mark.django_db
def test_l_ecran_public_ne_livre_aucun_nom_d_utilisateur(api, animateur) -> None:
    competition = _concours(groupes=2, questions=4, par=animateur)
    services.demarrer(competition)
    tour = competition.turns.first()
    services.lancer_tour(tour, client_uuid=uuid.uuid4())
    services.trancher(
        tour, outcome=TurnOutcome.CORRECT, client_uuid=uuid.uuid4(), par=animateur
    )

    rendu = str(api.get(reverse("ecran-public", args=[competition.code])).data)

    assert "jury" not in rendu
    assert "لجنة المسابقة" not in rendu


# --------------------------------------------------------------------------
# Droits
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_animer_exige_la_permission(api_student, animateur) -> None:
    competition = _concours(groupes=2, questions=4, par=animateur)

    reponse = api_student.post(
        reverse("competition-demarrer", args=[competition.id]), format="json"
    )

    assert reponse.status_code == status.HTTP_403_FORBIDDEN
    assert competition.turns.count() == 0


@pytest.mark.django_db
def test_le_jury_mene_un_tour_de_bout_en_bout(api_jury, animateur) -> None:
    """Parcours reel : demarrer, lancer, trancher, relire."""
    competition = _concours(groupes=2, questions=4, par=animateur)

    api_jury.post(reverse("competition-demarrer", args=[competition.id]), format="json")
    tour = competition.turns.order_by("index").first()

    lancement = api_jury.post(
        reverse("tour-lancer", args=[tour.id]),
        {"client_uuid": str(uuid.uuid4())},
        format="json",
    )
    decision = api_jury.post(
        reverse("tour-decider", args=[tour.id]),
        {"client_uuid": str(uuid.uuid4()), "outcome": "CORRECT"},
        format="json",
    )

    assert lancement.status_code == status.HTTP_200_OK
    assert lancement.data["started_at"] is not None
    assert decision.data["outcome"] == "CORRECT"
    assert decision.data["awarded_late"] is False


@pytest.mark.django_db
def test_le_deroule_est_livre_en_une_fois(api_jury, animateur) -> None:
    """La console doit pouvoir se passer du reseau ensuite."""
    competition = _concours(groupes=4, questions=12, par=animateur)
    api_jury.post(reverse("competition-demarrer", args=[competition.id]), format="json")

    corps = api_jury.get(
        reverse("competition-deroule", args=[competition.id])
    ).data

    assert len(corps["tours"]) == 12
    # Chaque tour porte son groupe et son enonce : aucune requete a resoudre.
    premier = corps["tours"][0]
    assert premier["group_name"] == "المجموعة 1"
    assert premier["question_text"] == "السؤال 1"
    assert corps["maintenant"] is not None
