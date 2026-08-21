"""
Endpoints de surveillance : journal, frequentation, deblocage, reinitialisation.

Deux choses sont verifiees a chaque fois : que la donnee est juste, et que la
porte est fermee a qui n'a pas le droit d'entrer.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db.models import F
from django.urls import reverse
from rest_framework import status

from apps.accounts import verrouillage
from apps.accounts.models import (
    Lockout,
    LoginAttempt,
    LoginOutcome,
    Role,
    User,
)


@pytest.fixture
def etudiantes(db) -> list[User]:
    comptes = []
    for matricule, nom in (("24501", "دعيه أدو"), ("24502", "أمينة محمدن")):
        user = User.objects.create_user(
            username=matricule, password=matricule * 2, full_name_ar=nom
        )
        user.role = Role.STUDENT
        user.save(update_fields=["role"])
        comptes.append(user)
    return comptes


def _visiter(user: User, fois: int) -> None:
    for _ in range(fois):
        verrouillage.enregistrer_succes(user, ip="41.188.1.2")


# --------------------------------------------------------------------------
# Journal
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_journal_liste_les_tentatives(api_admin, etudiantes) -> None:
    _visiter(etudiantes[0], 2)
    verrouillage.journaliser(
        "intrus", LoginOutcome.UNKNOWN_USER, ip="10.0.0.9", user_agent="curl/8"
    )

    reponse = api_admin.get(reverse("securite-journal"))

    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data["count"] == 3
    premiere = reponse.data["results"][0]
    assert premiere["username"] == "intrus"
    assert premiere["ip_address"] == "10.0.0.9"
    assert premiere["outcome"] == LoginOutcome.UNKNOWN_USER


@pytest.mark.django_db
def test_le_journal_se_filtre_sur_les_echecs(api_admin, etudiantes) -> None:
    _visiter(etudiantes[0], 2)
    verrouillage.journaliser("intrus", LoginOutcome.BAD_PASSWORD)

    reponse = api_admin.get(reverse("securite-journal"), {"succes": "0"})

    assert reponse.data["count"] == 1
    assert reponse.data["results"][0]["username"] == "intrus"


@pytest.mark.django_db
def test_le_journal_est_ferme_a_une_etudiante(api_student) -> None:
    assert (
        api_student.get(reverse("securite-journal")).status_code
        == status.HTTP_403_FORBIDDEN
    )


# --------------------------------------------------------------------------
# Frequentation
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_classement_des_visiteuses(api_admin, etudiantes) -> None:
    _visiter(etudiantes[0], 5)
    _visiter(etudiantes[1], 2)

    reponse = api_admin.get(reverse("securite-statistiques"))

    assert reponse.data["visites"] == 7
    assert reponse.data["visiteurs"] == 2
    top = reponse.data["top_etudiantes"]
    assert [(t["username"], t["visites"]) for t in top] == [("24501", 5), ("24502", 2)]
    assert top[0]["full_name_ar"] == "دعيه أدو"


@pytest.mark.django_db
def test_le_classement_ignore_le_personnel(api_admin, admin_user, etudiantes) -> None:
    """
    L'administration se connecte tous les jours : elle occuperait tout le
    tableau sans rien apprendre a personne.
    """
    _visiter(admin_user, 50)
    _visiter(etudiantes[0], 1)

    top = api_admin.get(reverse("securite-statistiques")).data["top_etudiantes"]

    assert [t["username"] for t in top] == ["24501"]


@pytest.mark.django_db
def test_le_classement_s_arrete_a_dix(api_admin, db) -> None:
    for i in range(1, 13):
        user = User.objects.create_user(username=f"246{i:02d}", password="x" * 12)
        user.role = Role.STUDENT
        user.save(update_fields=["role"])
        _visiter(user, i)

    top = api_admin.get(reverse("securite-statistiques")).data["top_etudiantes"]

    assert len(top) == 10
    # Les plus assidues d'abord.
    assert top[0]["visites"] == 12
    assert top[-1]["visites"] == 3


@pytest.mark.django_db
def test_la_periode_borne_le_decompte(api_admin, etudiantes) -> None:
    _visiter(etudiantes[0], 3)
    # Deux de ces visites datent d'il y a quarante jours.
    anciennes = LoginAttempt.objects.filter(username="24501")[:2]
    LoginAttempt.objects.filter(id__in=[a.id for a in anciennes]).update(
        at=F("at") - timedelta(days=40)
    )

    sur_trente = api_admin.get(reverse("securite-statistiques"), {"periode": "30"})
    sur_tout = api_admin.get(reverse("securite-statistiques"), {"periode": "tout"})

    assert sur_trente.data["visites"] == 1
    assert sur_tout.data["visites"] == 3


# --------------------------------------------------------------------------
# Deblocage
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_les_comptes_bloques_sont_listes(api_admin, etudiantes) -> None:
    verrouillage.enregistrer_echec(
        "24501", LoginOutcome.BAD_PASSWORD, user=etudiantes[0]
    )
    for _ in range(4):
        verrouillage.enregistrer_echec(
            "24501", LoginOutcome.BAD_PASSWORD, user=etudiantes[0]
        )

    reponse = api_admin.get(reverse("securite-verrous"))

    assert reponse.data["count"] == 1
    verrou = reponse.data["results"][0]
    assert verrou["username"] == "24501"
    assert verrou["full_name_ar"] == "دعيه أدو"
    assert verrou["actif"] is True
    assert verrou["duree_minutes"] == 5
    assert verrou["secondes_restantes"] > 0


@pytest.mark.django_db
def test_le_deblocage_rouvre_le_compte(api_admin, admin_user, etudiantes) -> None:
    for _ in range(5):
        verrouillage.enregistrer_echec(
            "24501", LoginOutcome.BAD_PASSWORD, user=etudiantes[0]
        )
    verrou = Lockout.objects.get()

    reponse = api_admin.post(
        reverse("securite-deverrouiller", args=[verrou.id]), format="json"
    )

    assert reponse.status_code == status.HTTP_200_OK
    verrou.refresh_from_db()
    assert verrou.released_at is not None
    assert verrou.released_by == admin_user
    assert verrouillage.verrou_actif("24501") is None


@pytest.mark.django_db
def test_le_blocage_reste_au_dossier_apres_deblocage(api_admin, etudiantes) -> None:
    """
    Le blocage est clos, pas efface : effacer l'incident retirerait a
    l'administration le seul indice d'une attaque en cours.
    """
    for _ in range(5):
        verrouillage.enregistrer_echec(
            "24501", LoginOutcome.BAD_PASSWORD, user=etudiantes[0]
        )
    verrou = Lockout.objects.get()
    api_admin.post(reverse("securite-deverrouiller", args=[verrou.id]), format="json")

    historique = api_admin.get(reverse("securite-verrous"), {"historique": "1"})

    assert historique.data["count"] == 1
    assert historique.data["results"][0]["actif"] is False
    assert Lockout.objects.count() == 1


@pytest.mark.django_db
def test_debloquer_deux_fois_est_refuse(api_admin, etudiantes) -> None:
    for _ in range(5):
        verrouillage.enregistrer_echec(
            "24501", LoginOutcome.BAD_PASSWORD, user=etudiantes[0]
        )
    verrou = Lockout.objects.get()
    api_admin.post(reverse("securite-deverrouiller", args=[verrou.id]), format="json")

    seconde = api_admin.post(
        reverse("securite-deverrouiller", args=[verrou.id]), format="json"
    )

    assert seconde.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_le_deblocage_est_ferme_a_une_etudiante(api_student, etudiantes) -> None:
    for _ in range(5):
        verrouillage.enregistrer_echec(
            "24501", LoginOutcome.BAD_PASSWORD, user=etudiantes[0]
        )
    verrou = Lockout.objects.get()

    reponse = api_student.post(
        reverse("securite-deverrouiller", args=[verrou.id]), format="json"
    )

    assert reponse.status_code == status.HTTP_403_FORBIDDEN


# --------------------------------------------------------------------------
# Reinitialisation de mot de passe
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_l_admin_reinitialise_sans_connaitre_l_ancien(api_admin, etudiantes) -> None:
    cible = etudiantes[0]

    reponse = api_admin.post(
        reverse("securite-reinitialiser", args=[cible.id]), format="json"
    )

    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data["genere"] is True
    nouveau = reponse.data["mot_de_passe"]

    cible.refresh_from_db()
    assert cible.check_password(nouveau)
    # Le mot de passe rendu est temporaire : son remplacement est impose.
    assert cible.must_change_password is True


@pytest.mark.django_db
def test_l_admin_peut_imposer_un_mot_de_passe(api_admin, etudiantes) -> None:
    cible = etudiantes[0]

    reponse = api_admin.post(
        reverse("securite-reinitialiser", args=[cible.id]),
        {"new_password": "2450124501"},
        format="json",
    )

    assert reponse.status_code == status.HTTP_200_OK
    assert reponse.data["genere"] is False
    cible.refresh_from_db()
    assert cible.check_password("2450124501")


@pytest.mark.django_db
def test_un_mot_de_passe_trop_court_est_refuse(api_admin, etudiantes) -> None:
    reponse = api_admin.post(
        reverse("securite-reinitialiser", args=[etudiantes[0].id]),
        {"new_password": "1234"},
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_huit_chiffres_sont_acceptes(api_admin, etudiantes) -> None:
    """
    La regle de l'etablissement : huit caracteres, numerique permis.

    Ce qui protege un tel mot de passe n'est pas sa longueur mais le
    verrouillage progressif — cinq essais, puis la porte se ferme.
    """
    reponse = api_admin.post(
        reverse("securite-reinitialiser", args=[etudiantes[0].id]),
        {"new_password": "24060240"},
        format="json",
    )

    assert reponse.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_la_reinitialisation_leve_le_blocage(api_admin, etudiantes) -> None:
    """Rendre un mot de passe sans rouvrir la porte n'aurait aucun sens."""
    for _ in range(5):
        verrouillage.enregistrer_echec(
            "24501", LoginOutcome.BAD_PASSWORD, user=etudiantes[0]
        )
    assert verrouillage.verrou_actif("24501") is not None

    reponse = api_admin.post(
        reverse("securite-reinitialiser", args=[etudiantes[0].id]), format="json"
    )

    assert reponse.data["verrous_leves"] == 1
    assert verrouillage.verrou_actif("24501") is None


@pytest.mark.django_db
def test_la_reinitialisation_est_fermee_a_une_etudiante(
    api_student, etudiantes
) -> None:
    reponse = api_student.post(
        reverse("securite-reinitialiser", args=[etudiantes[0].id]), format="json"
    )

    assert reponse.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_apres_reinitialisation_la_connexion_passe(api, api_admin, etudiantes) -> None:
    """Verification de bout en bout : le mot de passe rendu ouvre bien."""
    reponse = api_admin.post(
        reverse("securite-reinitialiser", args=[etudiantes[0].id]), format="json"
    )
    nouveau = reponse.data["mot_de_passe"]

    connexion = api.post(
        reverse("auth-login"),
        {"username": "24501", "password": nouveau},
        format="json",
    )

    assert connexion.status_code == status.HTTP_200_OK
    assert connexion.data["must_change_password"] is True
