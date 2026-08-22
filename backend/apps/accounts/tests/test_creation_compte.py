"""
Ouverture et correction des comptes.

Le nom complet est saisi, jamais deduit de l'identifiant : `sejad` n'apprend a
personne comment cette personne ecrit son nom. Pour une etudiante, le nom
existe deja dans son dossier et se reprend tel quel.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import Role, Student, User


@pytest.mark.django_db
def test_creation_d_un_compte_du_personnel(api_admin) -> None:
    reponse = api_admin.post(
        reverse("rbac-utilisateurs"),
        {
            "username": "khadija",
            "full_name_ar": "خديجة بنت أحمد",
            "password": "MotDePasse2026",
            "role": Role.ASSISTANT,
            "phone": "22334455",
        },
        format="json",
    )

    assert reponse.status_code == status.HTTP_201_CREATED
    compte = User.objects.get(username="khadija")
    # Le nom saisi, et non une translitteration de « khadija ».
    assert compte.full_name_ar == "خديجة بنت أحمد"
    assert compte.role == Role.ASSISTANT
    assert compte.phone == "22334455"
    assert compte.check_password("MotDePasse2026")
    # Le mot de passe a transite par une autre personne : il est provisoire.
    assert compte.must_change_password is True


@pytest.mark.django_db
def test_le_nom_complet_est_obligatoire(api_admin) -> None:
    reponse = api_admin.post(
        reverse("rbac-utilisateurs"),
        {"username": "sans-nom", "password": "MotDePasse2026", "role": Role.TEACHER},
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert "full_name_ar" in reponse.data


@pytest.mark.django_db
def test_un_identifiant_deja_pris_est_refuse(api_admin, admin_user) -> None:
    reponse = api_admin.post(
        reverse("rbac-utilisateurs"),
        {
            "username": admin_user.username.upper(),
            "full_name_ar": "شخص آخر",
            "password": "MotDePasse2026",
            "role": Role.TEACHER,
        },
        format="json",
    )

    # La comparaison ignore la casse : deux identifiants qui ne different que
    # par elle se confondraient a la saisie.
    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert "username" in reponse.data


@pytest.mark.django_db
def test_un_mot_de_passe_trop_court_est_refuse(api_admin) -> None:
    reponse = api_admin.post(
        reverse("rbac-utilisateurs"),
        {
            "username": "court",
            "full_name_ar": "اسم",
            "password": "1234",
            "role": Role.TEACHER,
        },
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST


# --------------------------------------------------------------------------
# Comptes d'etudiantes : le nom vient du dossier
# --------------------------------------------------------------------------


@pytest.fixture
def dossier(db) -> Student:
    return Student.objects.create(matricule="24500", full_name_ar="مريم اموه بديه")


@pytest.mark.django_db
def test_le_compte_d_une_etudiante_reprend_le_nom_du_dossier(
    api_admin, dossier
) -> None:
    reponse = api_admin.post(
        reverse("rbac-utilisateurs"), {"matricule": "24500"}, format="json"
    )

    assert reponse.status_code == status.HTTP_201_CREATED
    compte = User.objects.get(username="24500")
    assert compte.full_name_ar == "مريم اموه بديه"
    assert compte.role == Role.STUDENT
    # Regle de l'etablissement : le matricule ecrit deux fois.
    assert compte.check_password("2450024500")
    assert reponse.data["mot_de_passe"] == "2450024500"

    dossier.refresh_from_db()
    assert dossier.user == compte


@pytest.mark.django_db
def test_un_nom_saisi_ne_prime_pas_sur_le_dossier(api_admin, dossier) -> None:
    """Deux orthographes pour une meme personne, c'est une personne de trop."""
    api_admin.post(
        reverse("rbac-utilisateurs"),
        {"matricule": "24500", "full_name_ar": "اسم مختلف"},
        format="json",
    )

    assert User.objects.get(username="24500").full_name_ar == "مريم اموه بديه"


@pytest.mark.django_db
def test_un_compte_d_etudiante_exige_un_matricule(api_admin) -> None:
    reponse = api_admin.post(
        reverse("rbac-utilisateurs"),
        {
            "username": "libre",
            "full_name_ar": "طالبة",
            "password": "MotDePasse2026",
            "role": Role.STUDENT,
        },
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert "matricule" in reponse.data


@pytest.mark.django_db
def test_un_dossier_deja_pourvu_est_refuse(api_admin, dossier) -> None:
    api_admin.post(reverse("rbac-utilisateurs"), {"matricule": "24500"}, format="json")

    seconde = api_admin.post(
        reverse("rbac-utilisateurs"), {"matricule": "24500"}, format="json"
    )

    assert seconde.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_la_creation_est_fermee_a_une_etudiante(api_student) -> None:
    reponse = api_student.post(
        reverse("rbac-utilisateurs"),
        {
            "username": "intrus",
            "full_name_ar": "اسم",
            "password": "MotDePasse2026",
            "role": Role.ADMIN,
        },
        format="json",
    )

    assert reponse.status_code == status.HTTP_403_FORBIDDEN
    assert not User.objects.filter(username="intrus").exists()


# --------------------------------------------------------------------------
# Correction d'un nom
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_corriger_le_nom_d_un_compte(api_admin, teacher_user) -> None:
    reponse = api_admin.patch(
        reverse("rbac-utilisateur", args=[teacher_user.id]),
        {"full_name_ar": "محمد الأمين ولد أحمد"},
        format="json",
    )

    assert reponse.status_code == status.HTTP_200_OK
    teacher_user.refresh_from_db()
    assert teacher_user.full_name_ar == "محمد الأمين ولد أحمد"


@pytest.mark.django_db
def test_corriger_le_nom_suit_jusqu_au_dossier(api_admin, student, student_user) -> None:
    """Le dossier et le compte ne doivent pas porter deux noms differents."""
    api_admin.patch(
        reverse("rbac-utilisateur", args=[student_user.id]),
        {"full_name_ar": "فاطمة منت أدو"},
        format="json",
    )

    student.refresh_from_db()
    assert student.full_name_ar == "فاطمة منت أدو"


@pytest.mark.django_db
def test_un_nom_vide_est_refuse(api_admin, teacher_user) -> None:
    reponse = api_admin.patch(
        reverse("rbac-utilisateur", args=[teacher_user.id]),
        {"full_name_ar": "   "},
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
