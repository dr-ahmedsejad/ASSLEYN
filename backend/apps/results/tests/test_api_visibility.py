"""
Tests de visibilite des resultats.

Le point sensible : une etudiante ne doit voir que ses propres resultats, et
seulement apres publication du فصل. Ces tests forgent volontairement des URL
pour verifier que le filtrage tient au niveau du queryset, pas de l'affichage.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.academics.models import SemesterState
from apps.grading.models import Grade, GradeStatus
from apps.results.models import SemesterResult
from apps.results.services import recompute_semester


@pytest.fixture
def resultats(
    curriculum_a_quran, enrollment, autre_enrollment, fasl1, section_a, rule, admin_user
):
    """Deux etudiantes notees, section calculee."""
    Grade.objects.create(
        enrollment=enrollment,
        curriculum=curriculum_a_quran,
        value=Decimal("17"),
        status=GradeStatus.ENTERED,
        entered_by=admin_user,
    )
    Grade.objects.create(
        enrollment=autre_enrollment,
        curriculum=curriculum_a_quran,
        value=Decimal("9"),
        status=GradeStatus.ENTERED,
        entered_by=admin_user,
    )
    recompute_semester(fasl1, section_a)
    return SemesterResult.objects.all()


def publier(fasl1) -> None:
    fasl1.state = SemesterState.PUBLISHED
    fasl1.save(update_fields=["state"])


@pytest.mark.django_db
class TestVisibiliteEtudiante:
    def test_rien_avant_publication(self, api_student, resultats, fasl1) -> None:
        reponse = api_student.get(reverse("semester-result-list"))
        assert reponse.status_code == 200
        assert reponse.data["count"] == 0

    def test_ses_resultats_apres_publication(
        self, api_student, resultats, fasl1
    ) -> None:
        publier(fasl1)
        reponse = api_student.get(reverse("semester-result-list"))
        assert reponse.data["count"] == 1
        assert reponse.data["results"][0]["matricule"] == "24001"
        assert reponse.data["results"][0]["rank"] == 1
        assert reponse.data["results"][0]["cohort_size"] == 2

    def test_le_resultat_d_une_camarade_est_introuvable(
        self, api_student, resultats, fasl1, autre_enrollment
    ) -> None:
        """Meme en connaissant l'identifiant : 404, pas la donnee."""
        publier(fasl1)
        autre = SemesterResult.objects.get(enrollment=autre_enrollment)
        reponse = api_student.get(reverse("semester-result-detail", args=[autre.id]))
        assert reponse.status_code == 404

    def test_releve_personnel(self, api_student, resultats, fasl1) -> None:
        publier(fasl1)
        reponse = api_student.get(reverse("my-results"))
        assert reponse.status_code == 200
        assert len(reponse.data["semesters"]) == 1
        releve = reponse.data["semesters"][0]
        assert releve["average_display"] == "17.00"
        assert releve["decision_final"] == "PASSED"
        assert len(releve["subject_results"]) == 1
        assert releve["subject_results"][0]["subject_name"] == "القرآن الكريم"
        assert releve["subject_results"][0]["coefficient"] == "5.00"

    def test_releve_personnel_vide_avant_publication(
        self, api_student, resultats
    ) -> None:
        reponse = api_student.get(reverse("my-results"))
        assert reponse.data["semesters"] == []

    def test_releve_personnel_refuse_aux_autres_roles(
        self, api_teacher, api_admin
    ) -> None:
        # 403 : ce n'est pas la requête qui est mauvaise, c'est l'appelant qui
        # n'a pas de relevé — l'administration détient pourtant la permission.
        assert api_teacher.get(reverse("my-results")).status_code == 403
        assert api_admin.get(reverse("my-results")).status_code == 403

    def test_etudiante_ne_peut_pas_recalculer(self, api_student, fasl1) -> None:
        reponse = api_student.post(
            reverse("recompute"), {"semester": fasl1.id}, format="json"
        )
        assert reponse.status_code == 403


@pytest.mark.django_db
class TestVisibiliteEnseignant:
    def test_voit_les_resultats_de_sa_section(self, api_teacher, resultats) -> None:
        reponse = api_teacher.get(reverse("semester-result-list"))
        assert reponse.data["count"] == 2

    def test_ne_voit_pas_une_autre_section(
        self,
        api_teacher,
        resultats,
        enrollment_section_b,
        curriculum_b_quran,
        fasl1,
        section_b,
        rule,
        admin_user,
    ) -> None:
        Grade.objects.create(
            enrollment=enrollment_section_b,
            curriculum=curriculum_b_quran,
            value=Decimal("15"),
            status=GradeStatus.ENTERED,
            entered_by=admin_user,
        )
        recompute_semester(fasl1, section_b)
        assert SemesterResult.objects.count() == 3

        reponse = api_teacher.get(reverse("semester-result-list"))
        assert reponse.data["count"] == 2
        sections = {r["section_name"] for r in reponse.data["results"]}
        assert sections == {"المربيات"}

    def test_ne_peut_pas_surcharger_une_decision(self, api_teacher, resultats) -> None:
        resultat = SemesterResult.objects.filter(decision_computed="RESIT").first()
        reponse = api_teacher.post(
            reverse("semester-result-override", args=[resultat.id]),
            {"decision": "PASSED", "reason": "قرار المجلس"},
            format="json",
        )
        assert reponse.status_code == 403


@pytest.mark.django_db
class TestDeliberation:
    def test_surcharge_par_l_admin(self, api_admin, resultats, autre_enrollment) -> None:
        resultat = SemesterResult.objects.get(enrollment=autre_enrollment)
        assert resultat.decision_computed == "RESIT"

        reponse = api_admin.post(
            reverse("semester-result-override", args=[resultat.id]),
            {"decision": "PASSED", "reason": "قرار مجلس القسم بعد المداولة"},
            format="json",
        )
        assert reponse.status_code == 200
        resultat.refresh_from_db()
        assert resultat.decision_computed == "RESIT"
        assert resultat.decision_final == "PASSED"
        assert resultat.is_overridden is True
        assert resultat.overridden_by.username == "admin"

    def test_motif_obligatoire(self, api_admin, resultats, autre_enrollment) -> None:
        resultat = SemesterResult.objects.get(enrollment=autre_enrollment)
        reponse = api_admin.post(
            reverse("semester-result-override", args=[resultat.id]),
            {"decision": "PASSED", "reason": ""},
            format="json",
        )
        assert reponse.status_code == 400
        resultat.refresh_from_db()
        assert resultat.decision_final == "RESIT"

    def test_surcharge_impossible_apres_publication(
        self, api_admin, resultats, autre_enrollment, fasl1
    ) -> None:
        publier(fasl1)
        resultat = SemesterResult.objects.get(enrollment=autre_enrollment)
        reponse = api_admin.post(
            reverse("semester-result-override", args=[resultat.id]),
            {"decision": "PASSED", "reason": "قرار مجلس القسم"},
            format="json",
        )
        assert reponse.status_code == 400

    def test_recalcul_manuel_par_l_admin(self, api_admin, resultats, fasl1) -> None:
        reponse = api_admin.post(
            reverse("recompute"), {"semester": fasl1.id}, format="json"
        )
        assert reponse.status_code == 200
        assert reponse.data["recalcul"] == {"المربيات": 2}


@pytest.mark.django_db
class TestCoefficients:
    def test_admin_modifie_un_coefficient(
        self, api_admin, curriculum_a_quran, rule
    ) -> None:
        reponse = api_admin.patch(
            reverse("curriculum-detail", args=[curriculum_a_quran.id]),
            {"coefficient": "6.00"},
            format="json",
        )
        assert reponse.status_code == 200
        curriculum_a_quran.refresh_from_db()
        assert curriculum_a_quran.coefficient == Decimal("6.00")

    def test_enseignant_ne_peut_pas_modifier_un_coefficient(
        self, api_teacher, curriculum_a_quran, rule
    ) -> None:
        reponse = api_teacher.patch(
            reverse("curriculum-detail", args=[curriculum_a_quran.id]),
            {"coefficient": "6.00"},
            format="json",
        )
        assert reponse.status_code == 403

    def test_modification_refusee_apres_publication(
        self, api_admin, curriculum_a_quran, fasl1, rule
    ) -> None:
        publier(fasl1)
        reponse = api_admin.patch(
            reverse("curriculum-detail", args=[curriculum_a_quran.id]),
            {"coefficient": "6.00"},
            format="json",
        )
        assert reponse.status_code == 400

    def test_suppression_refusee_si_notes_existantes(
        self, api_admin, curriculum_a_quran, resultats
    ) -> None:
        reponse = api_admin.delete(
            reverse("curriculum-detail", args=[curriculum_a_quran.id])
        )
        assert reponse.status_code == 400

    def test_coefficient_negatif_refuse(
        self, api_admin, curriculum_a_quran, rule
    ) -> None:
        reponse = api_admin.patch(
            reverse("curriculum-detail", args=[curriculum_a_quran.id]),
            {"coefficient": "-1"},
            format="json",
        )
        assert reponse.status_code == 400
