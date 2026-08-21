"""
Contrôle d'accès par permissions.

Deux choses à prouver : les permissions effectives se calculent bien
(rôle + exceptions individuelles), et **les endpoints s'y tiennent** — sans
quoi filtrer le menu ne serait que du décor.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import Role, RolePermission, User, UserPermission
from apps.accounts.rbac import Permission
from conftest import MOT_DE_PASSE


@pytest.fixture
def assistant(db) -> User:
    user = User.objects.create_user(
        username="assistante",
        password=MOT_DE_PASSE,
        full_name_ar="مساعدة الإدارة",
    )
    user.role = Role.ASSISTANT
    user.save(update_fields=["role"])
    return user


@pytest.fixture
def api_assistant(assistant: User):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(assistant)
    return client


@pytest.mark.django_db
class TestPermissionsEffectives:
    def test_assistant_n_a_que_la_saisie(self, assistant: User) -> None:
        """Son écran est le poste de saisie, et rien d'autre."""
        assert assistant.permissions() == {Permission.NOTES_SAISIR}

    def test_le_menu_de_l_assistant_se_reduit_a_deux_entrees(
        self, api_assistant
    ) -> None:
        """
        Le front construit le menu à partir de cette liste : sans
        `tableau.consulter`, l'accueil disparaît lui aussi.
        """
        droits = set(api_assistant.get(reverse("auth-me")).data["permissions"])
        assert Permission.TABLEAU_CONSULTER not in droits
        assert Permission.NOTES_CONSULTER not in droits
        assert Permission.ETUDIANTES_GERER not in droits
        assert Permission.JOURNAL_CONSULTER not in droits

    def test_admin_a_tout(self, admin_user: User) -> None:
        assert admin_user.permissions() == set(Permission.values)

    def test_admin_garde_tout_meme_si_on_vide_la_table(
        self, admin_user: User
    ) -> None:
        """Aucune configuration ne prive l'administration d'une capacite."""
        RolePermission.objects.filter(role=Role.ADMIN).delete()
        assert admin_user.permissions() == set(Permission.values)

    def test_exception_individuelle_sans_effet_sur_un_admin(
        self, admin_user: User
    ) -> None:
        UserPermission.objects.create(
            user=admin_user, permission=Permission.NOTES_SAISIR, granted=False
        )
        assert Permission.NOTES_SAISIR in admin_user.permissions()

    def test_etudiante_n_a_que_son_releve(self, student_user: User) -> None:
        assert student_user.permissions() == {Permission.RESULTATS_PERSONNELS}

    def test_exception_individuelle_accorde(self, teacher_user: User) -> None:
        """Le droit se confie à une personne, sans changer son rôle."""
        assert Permission.DELIBERATION_GERER not in teacher_user.permissions()

        UserPermission.objects.create(
            user=teacher_user,
            permission=Permission.DELIBERATION_GERER,
            granted=True,
            reason="تكليف مؤقت",
        )
        assert Permission.DELIBERATION_GERER in teacher_user.permissions()
        # Le rôle, lui, n'a pas bougé.
        assert teacher_user.role == Role.TEACHER
        assert Permission.DELIBERATION_GERER not in teacher_user.permissions_du_role()

    def test_exception_individuelle_retire(self, teacher_user: User) -> None:
        assert Permission.NOTES_SAISIR in teacher_user.permissions()
        UserPermission.objects.create(
            user=teacher_user, permission=Permission.NOTES_SAISIR, granted=False
        )
        assert Permission.NOTES_SAISIR not in teacher_user.permissions()

    def test_retirer_au_role_retire_a_tous(self, teacher_user: User) -> None:
        RolePermission.objects.filter(
            role=Role.TEACHER, permission=Permission.NOTES_SAISIR
        ).delete()
        assert Permission.NOTES_SAISIR not in teacher_user.permissions()


@pytest.mark.django_db
class TestEndpointsSuiventLesPermissions:
    """Le menu peut cacher une entrée ; l'API doit refuser la requête."""

    def test_assistant_ne_peut_plus_lister_les_etudiantes(
        self, api_assistant, student
    ) -> None:
        assert api_assistant.get(reverse("student-list")).status_code == 403

    def test_assistant_ne_voit_pas_les_classements(
        self, api_assistant, fasl1, rule
    ) -> None:
        assert api_assistant.get(reverse("grade-list")).status_code == 403

    def test_assistant_ne_voit_pas_le_journal(self, api_assistant) -> None:
        assert api_assistant.get(reverse("grade-history-list")).status_code == 403

    def test_assistant_lit_et_ecrit_sa_grille(
        self, api_assistant, curriculum_a_quran, enrollment, fasl1, rule
    ) -> None:
        """Saisir suppose de lire : la grille et l'avancement restent ouverts."""
        assert (
            api_assistant.get(
                reverse("grade-sheet"), {"curriculum": curriculum_a_quran.id}
            ).status_code
            == 200
        )
        assert (
            api_assistant.get(
                reverse("grade-avancement"), {"semester": fasl1.id}
            ).status_code
            == 200
        )
        reponse = api_assistant.post(
            reverse("grade-sheet-bulk"),
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": enrollment.id, "value": "15.00"}],
            },
            format="json",
        )
        assert reponse.status_code == 200

    def test_l_assistant_saisit_dans_toutes_les_sections(
        self, api_assistant, curriculum_b_quran, enrollment_section_b, rule
    ) -> None:
        """Contrairement à l'enseignant, il n'est pas limité à des affectations."""
        reponse = api_assistant.post(
            reverse("grade-sheet-bulk"),
            {
                "curriculum": curriculum_b_quran.id,
                "grades": [
                    {"enrollment": enrollment_section_b.id, "value": "12.00"}
                ],
            },
            format="json",
        )
        assert reponse.status_code == 200

    def test_assistant_ne_peut_pas_deliberer(
        self, api_assistant, fasl1, rule
    ) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        assert api_assistant.post(f"{url}close/").status_code == 403

    def test_assistant_ne_peut_pas_gerer_les_comptes(self, api_assistant) -> None:
        assert api_assistant.get(reverse("teacher-list")).status_code == 403
        assert api_assistant.get(reverse("rbac-matrice")).status_code == 403

    def test_assistant_ne_peut_pas_modifier_un_coefficient(
        self, api_assistant, curriculum_a_quran, rule
    ) -> None:
        reponse = api_assistant.patch(
            reverse("curriculum-detail", args=[curriculum_a_quran.id]),
            {"coefficient": "6.00"},
            format="json",
        )
        assert reponse.status_code == 403

    def test_droit_individuel_ouvre_vraiment_l_endpoint(
        self, api_assistant, assistant, fasl1, rule
    ) -> None:
        """Confier la délibération à une personne doit ouvrir la route."""
        url = reverse("semester-detail", args=[fasl1.id])
        assert api_assistant.post(f"{url}close/").status_code == 403

        UserPermission.objects.create(
            user=assistant,
            permission=Permission.DELIBERATION_GERER,
            granted=True,
        )
        assert api_assistant.post(f"{url}close/").status_code == 200

    def test_retirer_la_saisie_a_un_enseignant_ferme_la_route(
        self, api_teacher, teacher_assigned, curriculum_a_quran, enrollment, rule
    ) -> None:
        charge = {
            "curriculum": curriculum_a_quran.id,
            "grades": [{"enrollment": enrollment.id, "value": "15.00"}],
        }
        url = reverse("grade-sheet-bulk")
        assert api_teacher.post(url, charge, format="json").status_code == 200

        UserPermission.objects.create(
            user=teacher_assigned.user,
            permission=Permission.NOTES_SAISIR,
            granted=False,
            reason="إيقاف مؤقت",
        )
        assert api_teacher.post(url, charge, format="json").status_code == 403

    def test_etudiante_reste_enfermee(self, api_student, fasl1, rule) -> None:
        assert api_student.get(reverse("student-list")).status_code == 403
        assert api_student.get(reverse("rbac-matrice")).status_code == 403


@pytest.mark.django_db
class TestMatriceDesDroits:
    def test_lecture(self, api_admin) -> None:
        reponse = api_admin.get(reverse("rbac-matrice"))
        assert reponse.status_code == 200
        roles = {r["code"] for r in reponse.data["roles"]}
        assert roles == {"ADMIN", "ASSISTANT", "TEACHER", "STUDENT"}

        codes = {
            p["code"]
            for categorie in reponse.data["categories"]
            for p in categorie["permissions"]
        }
        assert codes == set(Permission.values)

    def test_accorder_une_permission_a_un_role(self, api_admin) -> None:
        reponse = api_admin.put(
            reverse("rbac-matrice"),
            {
                "attributions": [
                    {
                        "role": "ASSISTANT",
                        "permission": Permission.DELIBERATION_GERER,
                        "accordee": True,
                    }
                ]
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["accordees"] == 1
        assert RolePermission.objects.filter(
            role="ASSISTANT", permission=Permission.DELIBERATION_GERER
        ).exists()

    @pytest.mark.parametrize(
        "code",
        [Permission.COMPTES_GERER, Permission.NOTES_SAISIR, Permission.ANNEES_GERER],
    )
    def test_aucun_droit_de_l_admin_n_est_retirable(self, api_admin, code) -> None:
        """L'administration peut tout, et ne peut pas s'en priver."""
        reponse = api_admin.put(
            reverse("rbac-matrice"),
            {"attributions": [{"role": "ADMIN", "permission": code, "accordee": False}]},
            format="json",
        )
        assert reponse.status_code == 400
        assert RolePermission.objects.filter(role="ADMIN", permission=code).exists()

    def test_toutes_les_cases_admin_sont_verrouillees(self, api_admin) -> None:
        reponse = api_admin.get(reverse("rbac-matrice"))
        cases = [
            p["roles"]["ADMIN"]
            for categorie in reponse.data["categories"]
            for p in categorie["permissions"]
        ]
        assert all(c["verrouillee"] and c["accordee"] for c in cases)

    def test_enseignant_ne_peut_pas_modifier_la_matrice(self, api_teacher) -> None:
        reponse = api_teacher.put(
            reverse("rbac-matrice"),
            {
                "attributions": [
                    {
                        "role": "TEACHER",
                        "permission": Permission.COMPTES_GERER,
                        "accordee": True,
                    }
                ]
            },
            format="json",
        )
        assert reponse.status_code == 403


@pytest.mark.django_db
class TestDroitsIndividuels:
    def test_liste_exclut_les_etudiantes(
        self, api_admin, student, teacher_user, assistant
    ) -> None:
        reponse = api_admin.get(reverse("rbac-utilisateurs"))
        assert reponse.status_code == 200
        roles = {u["role"] for u in reponse.data}
        assert "STUDENT" not in roles
        assert {"ADMIN", "TEACHER", "ASSISTANT"} <= roles

    def test_recherche_par_nom(self, api_admin, assistant) -> None:
        reponse = api_admin.get(reverse("rbac-utilisateurs"), {"search": "assistante"})
        assert [u["username"] for u in reponse.data] == ["assistante"]

    def test_detail_montre_l_origine_du_droit(self, api_admin, assistant) -> None:
        reponse = api_admin.get(reverse("rbac-utilisateur", args=[assistant.id]))
        assert reponse.status_code == 200
        par_code = {p["code"]: p for p in reponse.data["permissions"]}

        saisie = par_code[Permission.NOTES_SAISIR]
        assert saisie["par_le_role"] is True
        assert saisie["exception"] is None
        assert saisie["effective"] is True

        deliberation = par_code[Permission.DELIBERATION_GERER]
        assert deliberation["par_le_role"] is False
        assert deliberation["effective"] is False

    def test_accorder_la_saisie_a_une_personne(
        self, api_admin, teacher_user
    ) -> None:
        UserPermission.objects.filter(user=teacher_user).delete()
        reponse = api_admin.put(
            reverse("rbac-utilisateur", args=[teacher_user.id]),
            {
                "exceptions": [
                    {
                        "permission": Permission.ETUDIANTES_GERER,
                        "granted": True,
                        "reason": "تكليف",
                    }
                ]
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["posees"] == 1
        teacher_user.refresh_from_db()
        assert Permission.ETUDIANTES_GERER in teacher_user.permissions()

    def test_lever_une_exception_rend_au_role(self, api_admin, teacher_user) -> None:
        UserPermission.objects.create(
            user=teacher_user, permission=Permission.NOTES_SAISIR, granted=False
        )
        assert Permission.NOTES_SAISIR not in teacher_user.permissions()

        reponse = api_admin.put(
            reverse("rbac-utilisateur", args=[teacher_user.id]),
            {"exceptions": [{"permission": Permission.NOTES_SAISIR, "granted": None}]},
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["levees"] == 1
        assert Permission.NOTES_SAISIR in teacher_user.permissions()

    def test_pas_d_exception_pour_un_admin(self, api_admin, admin_user) -> None:
        reponse = api_admin.put(
            reverse("rbac-utilisateur", args=[admin_user.id]),
            {"exceptions": [{"permission": Permission.NOTES_SAISIR, "granted": False}]},
            format="json",
        )
        assert reponse.status_code == 400

    def test_pas_d_exception_pour_une_etudiante(
        self, api_admin, student_user
    ) -> None:
        reponse = api_admin.put(
            reverse("rbac-utilisateur", args=[student_user.id]),
            {"exceptions": [{"permission": Permission.NOTES_SAISIR, "granted": True}]},
            format="json",
        )
        assert reponse.status_code == 400
        assert UserPermission.objects.count() == 0


@pytest.mark.django_db
def test_me_expose_les_permissions(api_assistant) -> None:
    """Le front construit sa navigation à partir de cette liste."""
    reponse = api_assistant.get(reverse("auth-me"))
    assert reponse.status_code == 200
    assert reponse.data["role"] == "ASSISTANT"
    assert reponse.data["permissions"] == [Permission.NOTES_SAISIR]
