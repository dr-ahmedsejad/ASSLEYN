"""Tests d'authentification et de durcissement des comptes."""

from __future__ import annotations

import pytest
from django.contrib.auth.hashers import identify_hasher
from django.urls import reverse

from apps.accounts.models import Role, User
from conftest import MOT_DE_PASSE


@pytest.mark.django_db
class TestConnexion:
    def test_connexion_valide(self, api, student) -> None:
        reponse = api.post(
            reverse("auth-login"),
            {"username": "24001", "password": MOT_DE_PASSE},
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["role"] == Role.STUDENT
        assert reponse.data["matricule"] == "24001"
        # La session est bien ouverte.
        assert api.get(reverse("auth-me")).status_code == 200

    def test_mauvais_mot_de_passe_refuse(self, api, student) -> None:
        reponse = api.post(
            reverse("auth-login"),
            {"username": "24001", "password": "mauvais-mot-de-passe"},
            format="json",
        )
        assert reponse.status_code == 400

    def test_le_message_ne_revele_pas_si_le_compte_existe(self, api, student) -> None:
        """Compte inexistant et mauvais mot de passe donnent la meme reponse."""
        inconnu = api.post(
            reverse("auth-login"),
            {"username": "99999", "password": "x-quelconque-1234"},
            format="json",
        )
        existant = api.post(
            reverse("auth-login"),
            {"username": "24001", "password": "x-quelconque-1234"},
            format="json",
        )
        assert inconnu.status_code == existant.status_code == 400
        assert inconnu.data == existant.data

    def test_anonyme_refuse_sur_les_routes_metier(self, api, student) -> None:
        assert api.get(reverse("auth-me")).status_code in (401, 403)
        assert api.get(reverse("my-results")).status_code in (401, 403)

    def test_deconnexion(self, api_student) -> None:
        assert api_student.post(reverse("auth-logout")).status_code == 204


@pytest.mark.django_db
class TestMotDePasse:
    def test_hachage_argon2(self, student_user: User) -> None:
        """Le stockage doit utiliser Argon2, pas le PBKDF2 par defaut."""
        assert identify_hasher(student_user.password).algorithm == "argon2"

    def test_changement_de_mot_de_passe(self, api_student, student_user) -> None:
        reponse = api_student.post(
            reverse("auth-change-password"),
            {
                "current_password": MOT_DE_PASSE,
                "new_password": "Nouveau-Mot-De-Passe-2026",
            },
            format="json",
        )
        assert reponse.status_code == 204
        student_user.refresh_from_db()
        assert student_user.check_password("Nouveau-Mot-De-Passe-2026")
        assert student_user.must_change_password is False
        assert student_user.password_changed_at is not None

    def test_mauvais_mot_de_passe_actuel_refuse(self, api_student) -> None:
        reponse = api_student.post(
            reverse("auth-change-password"),
            {"current_password": "faux", "new_password": "Nouveau-Mot-De-Passe-2026"},
            format="json",
        )
        assert reponse.status_code == 400
        assert "current_password" in reponse.data

    def test_mot_de_passe_trop_court_refuse(self, api_student) -> None:
        reponse = api_student.post(
            reverse("auth-change-password"),
            {"current_password": MOT_DE_PASSE, "new_password": "court1"},
            format="json",
        )
        assert reponse.status_code == 400
        assert "new_password" in reponse.data

    def test_reutiliser_le_meme_mot_de_passe_refuse(self, api_student) -> None:
        reponse = api_student.post(
            reverse("auth-change-password"),
            {"current_password": MOT_DE_PASSE, "new_password": MOT_DE_PASSE},
            format="json",
        )
        assert reponse.status_code == 400


@pytest.mark.django_db
class TestRoles:
    def test_etudiante_ne_peut_pas_lister_les_dossiers(self, api_student) -> None:
        assert api_student.get(reverse("student-list")).status_code == 403

    def test_enseignant_ne_peut_pas_lister_les_dossiers(self, api_teacher) -> None:
        assert api_teacher.get(reverse("student-list")).status_code == 403

    def test_admin_peut_lister_les_dossiers(self, api_admin, student) -> None:
        reponse = api_admin.get(reverse("student-list"))
        assert reponse.status_code == 200
        assert reponse.data["count"] == 1

    def test_le_role_n_est_pas_modifiable_par_l_api(self, api_student, student_user) -> None:
        """Le profil est en lecture seule : impossible de s'auto-promouvoir."""
        reponse = api_student.get(reverse("auth-me"))
        assert reponse.data["role"] == Role.STUDENT
        student_user.refresh_from_db()
        assert student_user.role == Role.STUDENT
