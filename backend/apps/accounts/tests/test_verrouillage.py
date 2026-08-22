"""
Verrouillage progressif et journal des connexions.

Ce qui est verifie ici, c'est la regle telle que l'etablissement l'a enoncee :
cinq essais, puis 5 minutes ; cinq de plus, 15 minutes ; cinq encore, 30
minutes. Et le fait qu'un compte bloque ne repond plus, meme au bon mot de
passe — sans quoi le blocage deviendrait un oracle.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db.models import F
from django.urls import reverse
from rest_framework import status

from apps.accounts import verrouillage
from apps.accounts.models import Lockout, LoginAttempt, LoginOutcome, Role, User

MOT_DE_PASSE = "2406024060"


@pytest.fixture
def etudiante(db) -> User:
    user = User.objects.create_user(
        username="24060", password=MOT_DE_PASSE, full_name_ar="الدودو حسن"
    )
    user.role = Role.STUDENT
    user.save(update_fields=["role"])
    return user


def _connexion(client, username: str, password: str):
    return client.post(
        reverse("auth-login"),
        {"username": username, "password": password},
        format="json",
    )


def _echouer(client, fois: int, username: str = "24060"):
    reponses = []
    for _ in range(fois):
        reponses.append(_connexion(client, username, "mauvais-mot-de-passe"))
    return reponses


def _faire_passer_le_temps(username: str = "24060", minutes: int = 31) -> None:
    """
    Simule l'ecoulement du temps plutot que de l'attendre.

    On recule les traces — tentatives et blocage — au lieu d'avancer `until`.
    Deplacer la seule date de fin la ferait passer AVANT les echecs qu'elle
    sanctionne, un etat que la realite ne produit jamais : le test mesurerait
    alors une situation impossible.
    """
    ecoule = timedelta(minutes=minutes)
    LoginAttempt.objects.filter(username=username).update(at=F("at") - ecoule)
    Lockout.objects.filter(username=username).update(
        started_at=F("started_at") - ecoule, until=F("until") - ecoule
    )


# --------------------------------------------------------------------------
# Comptage et paliers
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_quatre_echecs_ne_bloquent_pas(api, etudiante) -> None:
    reponses = _echouer(api, 4)

    assert all(r.status_code == status.HTTP_400_BAD_REQUEST for r in reponses)
    # Le compte a rebours des essais est visible : c'est ce qui permet a
    # l'interface de prevenir avant la fermeture.
    assert [r.data["tentatives_restantes"] for r in reponses] == [4, 3, 2, 1]
    assert verrouillage.verrou_actif("24060") is None


@pytest.mark.django_db
def test_cinquieme_echec_bloque_cinq_minutes(api, etudiante) -> None:
    reponses = _echouer(api, 5)

    derniere = reponses[-1]
    assert derniere.status_code == status.HTTP_423_LOCKED
    assert derniere.data["verrouille"] is True
    assert derniere.data["niveau"] == 1
    assert 4 * 60 < derniere.data["secondes_restantes"] <= 5 * 60

    verrou = verrouillage.verrou_actif("24060")
    assert verrou is not None
    assert verrou.level == 1


@pytest.mark.django_db
def test_le_bon_mot_de_passe_ne_rouvre_pas_un_compte_bloque(
    api, etudiante
) -> None:
    _echouer(api, 5)

    reponse = _connexion(api, "24060", MOT_DE_PASSE)

    assert reponse.status_code == status.HTTP_423_LOCKED
    # La tentative est tracee, mais rien ne dit que le mot de passe etait bon.
    assert "verrouille" in reponse.data
    assert LoginAttempt.objects.filter(outcome=LoginOutcome.LOCKED).count() == 1


@pytest.mark.django_db
def test_les_paliers_montent_a_15_puis_30_minutes(api, etudiante) -> None:
    durees = []
    for _ in range(3):
        _echouer(api, 5)
        verrou = Lockout.objects.filter(username="24060").order_by("-started_at").first()
        durees.append(round((verrou.until - verrou.started_at).total_seconds() / 60))
        _faire_passer_le_temps()

    assert durees == [5, 15, 30]


@pytest.mark.django_db
def test_le_palier_plafonne_a_trente_minutes(api, etudiante) -> None:
    """Au-dela du troisieme palier, allonger encore ne protegerait pas mieux."""
    for _ in range(4):
        _echouer(api, 5)
        _faire_passer_le_temps()

    dernier = Lockout.objects.order_by("-started_at").first()
    assert dernier.level == 4
    assert round((dernier.until - dernier.started_at).total_seconds() / 60) == 30


@pytest.mark.django_db
def test_apres_expiration_cinq_nouveaux_essais(api, etudiante) -> None:
    _echouer(api, 5)
    _faire_passer_le_temps()

    etat = verrouillage.etat("24060")

    assert etat.verrouille is False
    assert etat.tentatives_restantes == verrouillage.LIMITE_TENTATIVES


@pytest.mark.django_db
def test_une_reussite_remet_le_compteur_a_zero(api, etudiante) -> None:
    _echouer(api, 3)
    assert _connexion(api, "24060", MOT_DE_PASSE).status_code == 200

    assert verrouillage.echecs_consecutifs("24060") == 0
    assert verrouillage.etat("24060").tentatives_restantes == 5


@pytest.mark.django_db
def test_apres_deblocage_les_echecs_recomptent(api, etudiante, admin_user) -> None:
    """
    Deverrouiller ne doit pas ouvrir une fenetre libre.

    Le blocage court jusqu'a une heure future ; si le compteur repartait de
    cette heure-la, celui qui insiste juste apres le deblocage ne serait plus
    jamais bloque avant l'expiration initiale.
    """
    _echouer(api, 5)
    verrou = Lockout.objects.get(username="24060")
    verrouillage.deverrouiller(verrou, par=admin_user)

    _echouer(api, 4)
    assert verrouillage.echecs_consecutifs("24060") == 4

    derniere = _echouer(api, 1)[0]
    assert derniere.status_code == status.HTTP_423_LOCKED


# --------------------------------------------------------------------------
# Isolation : un compte bloque n'en bloque aucun autre
# --------------------------------------------------------------------------


@pytest.fixture
def camarade(db) -> User:
    """Une seconde etudiante, du meme قسم et derriere la meme sortie internet."""
    user = User.objects.create_user(
        username="24061", password="2406124061", full_name_ar="عيشة منت باباه"
    )
    user.role = Role.STUDENT
    user.save(update_fields=["role"])
    return user


@pytest.mark.django_db
def test_le_blocage_n_atteint_que_le_compte_vise(api, etudiante, camarade) -> None:
    """
    Le point le plus important de toute la mecanique.

    Bloquer un compte ne doit rien fermer a personne d'autre — surtout pas
    depuis la meme adresse : l'institut sort par une seule connexion internet,
    et toutes les etudiantes consultent leurs resultats depuis ce reseau.
    """
    _echouer(api, 5, username="24060")
    assert verrouillage.verrou_actif("24060") is not None

    reponse = _connexion(api, "24061", "2406124061")

    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data["username"] == "24061"
    assert verrouillage.verrou_actif("24061") is None


@pytest.mark.django_db
def test_toute_une_classe_passe_pendant_qu_un_compte_est_bloque(api, etudiante) -> None:
    """Le meme point, a l'echelle ou il se pose vraiment : depuis une seule IP."""
    _echouer(api, 5, username="24060")

    for numero in range(24062, 24082):
        matricule = str(numero)
        compte = User.objects.create_user(
            username=matricule, password=matricule * 2, full_name_ar=f"طالبة {numero}"
        )
        compte.role = Role.STUDENT
        compte.save(update_fields=["role"])

        reponse = api.post(
            reverse("auth-login"),
            {"username": matricule, "password": matricule * 2},
            format="json",
            REMOTE_ADDR="41.188.1.2",
        )
        assert reponse.status_code == status.HTTP_200_OK, matricule

    # Et le compte vise, lui, reste ferme.
    assert verrouillage.verrou_actif("24060") is not None
    assert Lockout.objects.count() == 1


@pytest.mark.django_db
def test_les_echecs_ne_se_melangent_pas_entre_comptes(api, etudiante, camarade) -> None:
    """Quatre erreurs chacune ne bloquent personne : les compteurs sont separes."""
    _echouer(api, 4, username="24060")
    _echouer(api, 4, username="24061")

    assert verrouillage.echecs_consecutifs("24060") == 4
    assert verrouillage.echecs_consecutifs("24061") == 4
    assert Lockout.objects.count() == 0


@pytest.mark.django_db
def test_le_blocage_suit_le_compte_et_non_l_adresse(api, etudiante) -> None:
    """
    Changer de reseau ne contourne pas le blocage.

    C'est le revers du choix precedent : puisque le verrou porte sur le compte,
    il le suit partout — telephone, domicile, etablissement.
    """
    for _ in range(5):
        api.post(
            reverse("auth-login"),
            {"username": "24060", "password": "faux"},
            format="json",
            REMOTE_ADDR="41.188.1.2",
        )

    depuis_ailleurs = api.post(
        reverse("auth-login"),
        {"username": "24060", "password": MOT_DE_PASSE},
        format="json",
        REMOTE_ADDR="196.20.9.9",
    )

    assert depuis_ailleurs.status_code == status.HTTP_423_LOCKED


@pytest.mark.django_db
def test_le_deblocage_d_un_compte_ne_touche_pas_les_autres(
    api, etudiante, camarade, admin_user
) -> None:
    _echouer(api, 5, username="24060")
    _echouer(api, 5, username="24061")
    assert Lockout.objects.filter(released_at__isnull=True).count() == 2

    verrouillage.deverrouiller(verrouillage.verrou_actif("24060"), par=admin_user)

    assert verrouillage.verrou_actif("24060") is None
    assert verrouillage.verrou_actif("24061") is not None


# --------------------------------------------------------------------------
# Journal
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_journal_distingue_les_issues(api, etudiante) -> None:
    _connexion(api, "24060", "mauvais")
    _connexion(api, "inconnue", "mauvais")
    _connexion(api, "24060", MOT_DE_PASSE)

    issues = list(LoginAttempt.objects.order_by("at").values_list("outcome", flat=True))
    assert issues == [
        LoginOutcome.BAD_PASSWORD,
        LoginOutcome.UNKNOWN_USER,
        LoginOutcome.SUCCESS,
    ]


@pytest.mark.django_db
def test_le_journal_retient_l_identifiant_inconnu(api, db) -> None:
    """L'identifiant essaye est conserve tel quel : c'est tout l'interet."""
    _connexion(api, "n-existe-pas", "essai")

    trace = LoginAttempt.objects.get()
    assert trace.username == "n-existe-pas"
    assert trace.user is None
    assert trace.outcome == LoginOutcome.UNKNOWN_USER


@pytest.mark.django_db
def test_le_journal_enregistre_l_adresse(api, etudiante) -> None:
    api.post(
        reverse("auth-login"),
        {"username": "24060", "password": "mauvais"},
        format="json",
        REMOTE_ADDR="10.20.30.40",
    )

    assert LoginAttempt.objects.get().ip_address == "10.20.30.40"


@pytest.mark.django_db
def test_l_adresse_derriere_un_proxy_est_celle_du_client(api, etudiante) -> None:
    """Nginx transmet l'adresse d'origine ; sans cela tout viendrait du proxy."""
    api.post(
        reverse("auth-login"),
        {"username": "24060", "password": "mauvais"},
        format="json",
        HTTP_X_FORWARDED_FOR="41.188.1.2, 172.18.0.5",
        REMOTE_ADDR="172.18.0.5",
    )

    assert LoginAttempt.objects.get().ip_address == "41.188.1.2"


@pytest.mark.django_db
def test_la_reponse_ne_revele_pas_l_existence_du_compte(api, etudiante) -> None:
    inconnue = _connexion(api, "personne", "essai")
    connue = _connexion(api, "24060", "mauvais")

    assert inconnue.data["detail"] == connue.data["detail"]
