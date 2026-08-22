"""
Liste de tous les comptes.

A distinguer de la liste des droits individuels, qui ne montre que le
personnel : celle-ci repond a « qui possede un compte », etudiantes comprises.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts import verrouillage
from apps.accounts.models import LoginOutcome, Role, User


@pytest.mark.django_db
def test_la_liste_contient_les_etudiantes(api_admin, student, student_user) -> None:
    """
    Le point qui manquait : la liste des droits exclut les etudiantes, si bien
    qu'aucun ecran ne montrait leur compte.
    """
    reponse = api_admin.get(reverse("rbac-comptes"))

    assert reponse.status_code == status.HTTP_200_OK
    comptes = {c["username"]: c for c in reponse.data["results"]}
    assert student_user.username in comptes
    assert comptes[student_user.username]["matricule"] == student.matricule
    assert comptes[student_user.username]["role"] == Role.STUDENT


@pytest.mark.django_db
def test_la_liste_est_paginee(api_admin, db) -> None:
    for numero in range(24200, 24230):
        User.objects.create_user(username=str(numero), password=str(numero) * 2)

    reponse = api_admin.get(reverse("rbac-comptes"), {"page_size": 10})

    assert reponse.data["count"] >= 30
    assert len(reponse.data["results"]) == 10


@pytest.mark.django_db
def test_filtre_par_role(api_admin, admin_user, student_user) -> None:
    reponse = api_admin.get(reverse("rbac-comptes"), {"role": Role.STUDENT})

    roles = {c["role"] for c in reponse.data["results"]}
    assert roles == {Role.STUDENT}


@pytest.mark.django_db
def test_recherche_sur_le_nom_et_l_identifiant(api_admin, teacher_user) -> None:
    teacher_user.full_name_ar = "محمد الأمين"
    teacher_user.save(update_fields=["full_name_ar"])

    par_nom = api_admin.get(reverse("rbac-comptes"), {"search": "الأمين"})
    par_identifiant = api_admin.get(
        reverse("rbac-comptes"), {"search": teacher_user.username}
    )

    assert [c["id"] for c in par_nom.data["results"]] == [teacher_user.id]
    assert [c["id"] for c in par_identifiant.data["results"]] == [teacher_user.id]


@pytest.mark.django_db
def test_les_comptes_fermes_sont_signales(api_admin, student_user) -> None:
    for _ in range(5):
        verrouillage.enregistrer_echec(
            student_user.username, LoginOutcome.BAD_PASSWORD, user=student_user
        )

    reponse = api_admin.get(reverse("rbac-comptes"), {"verrouilles": "1"})

    assert [c["username"] for c in reponse.data["results"]] == [student_user.username]
    assert reponse.data["results"][0]["verrouille"] is True


@pytest.mark.django_db
def test_filtre_mot_de_passe_provisoire(api_admin, admin_user, student_user) -> None:
    student_user.must_change_password = True
    student_user.save(update_fields=["must_change_password"])

    reponse = api_admin.get(reverse("rbac-comptes"), {"mdp_provisoire": "1"})

    assert [c["username"] for c in reponse.data["results"]] == [student_user.username]


@pytest.mark.django_db
def test_la_liste_ne_contient_aucune_empreinte_de_mot_de_passe(
    api_admin, student_user
) -> None:
    """Une liste de comptes n'a aucune raison de transporter des empreintes."""
    reponse = api_admin.get(reverse("rbac-comptes"))

    for compte in reponse.data["results"]:
        assert "password" not in compte


@pytest.mark.django_db
def test_la_liste_est_fermee_a_une_etudiante(api_student) -> None:
    assert (
        api_student.get(reverse("rbac-comptes")).status_code
        == status.HTTP_403_FORBIDDEN
    )


@pytest.mark.django_db
def test_le_plafond_de_taille_de_page_est_respecte(api_admin, db) -> None:
    """
    Une taille de page sans borne serait un moyen simple de charger toute la
    base en une requete.
    """
    for numero in range(24300, 24310):
        User.objects.create_user(username=str(numero), password=str(numero) * 2)

    reponse = api_admin.get(reverse("rbac-comptes"), {"page_size": 100000})

    assert len(reponse.data["results"]) <= 200
