"""
Ouverture de l'année suivante et réinscription des étudiantes.

Tout est rattaché à l'année : dupliquer la structure ne doit jamais entraîner
les notes ni les résultats de l'année précédente.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    Semester,
    SemesterState,
)
from apps.accounts.models import Student
from apps.grading.models import Grade, GradeStatus, GradingRule


@pytest.fixture
def annee_garnie(year, fasl1, fasl2, curriculum_a_quran, curriculum_a_fiqh, rule):
    """Une année complète : deux فصول et deux matières au programme."""
    return year


@pytest.mark.django_db
class TestOuvertureAnneeSuivante:
    def test_duplication_de_la_structure(self, api_admin, annee_garnie) -> None:
        reponse = api_admin.post(
            reverse("year-dupliquer", args=[annee_garnie.id]),
            {
                "label": "2026-2027",
                "start_date": "2026-10-01",
                "end_date": "2027-06-30",
                "activer": True,
            },
            format="json",
        )
        assert reponse.status_code == 201
        assert reponse.data["fusul_crees"] == 2
        assert reponse.data["programmes_copies"] == 2

        cible = AcademicYear.objects.get(label="2026-2027")
        assert cible.is_active is True
        # Une seule année active à la fois.
        annee_garnie.refresh_from_db()
        assert annee_garnie.is_active is False

        fusul = Semester.objects.filter(year=cible).order_by("number")
        assert [f.number for f in fusul] == [1, 2]
        assert all(f.state == SemesterState.DRAFT for f in fusul)
        # Les dates sont décalées d'un an, jamais vides.
        assert fusul[0].start_date.year == 2026

    def test_les_coefficients_sont_repris(self, api_admin, annee_garnie) -> None:
        api_admin.post(
            reverse("year-dupliquer", args=[annee_garnie.id]),
            {
                "label": "2026-2027",
                "start_date": "2026-10-01",
                "end_date": "2027-06-30",
            },
            format="json",
        )
        cible = AcademicYear.objects.get(label="2026-2027")
        programmes = Curriculum.objects.filter(semester__year=cible)
        assert programmes.count() == 2
        assert programmes.get(subject__code="QURAN").coefficient == Decimal("5.00")
        assert programmes.get(subject__code="FIQH").coefficient == Decimal("3.00")

    def test_ni_notes_ni_inscriptions_ne_suivent(
        self, api_admin, annee_garnie, enrollment, curriculum_a_quran, admin_user
    ) -> None:
        Grade.objects.create(
            enrollment=enrollment,
            curriculum=curriculum_a_quran,
            value=Decimal("15"),
            status=GradeStatus.ENTERED,
            entered_by=admin_user,
        )
        api_admin.post(
            reverse("year-dupliquer", args=[annee_garnie.id]),
            {
                "label": "2026-2027",
                "start_date": "2026-10-01",
                "end_date": "2027-06-30",
            },
            format="json",
        )
        cible = AcademicYear.objects.get(label="2026-2027")
        assert Enrollment.objects.filter(year=cible).count() == 0
        assert Grade.objects.filter(curriculum__semester__year=cible).count() == 0
        # L'année précédente est intacte.
        assert Grade.objects.filter(curriculum=curriculum_a_quran).count() == 1

    def test_un_reglement_est_cree_pour_la_nouvelle_annee(
        self, api_admin, annee_garnie
    ) -> None:
        api_admin.post(
            reverse("year-dupliquer", args=[annee_garnie.id]),
            {
                "label": "2026-2027",
                "start_date": "2026-10-01",
                "end_date": "2027-06-30",
            },
            format="json",
        )
        cible = AcademicYear.objects.get(label="2026-2027")
        regle = GradingRule.objects.get(year=cible, section__isnull=True)
        assert regle.pass_threshold == Decimal("10")

    def test_libelle_deja_pris_refuse(self, api_admin, annee_garnie) -> None:
        reponse = api_admin.post(
            reverse("year-dupliquer", args=[annee_garnie.id]),
            {
                "label": "2025-2026",
                "start_date": "2026-10-01",
                "end_date": "2027-06-30",
            },
            format="json",
        )
        assert reponse.status_code == 400

    def test_dates_incoherentes_refusees(self, api_admin, annee_garnie) -> None:
        reponse = api_admin.post(
            reverse("year-dupliquer", args=[annee_garnie.id]),
            {
                "label": "2026-2027",
                "start_date": "2027-06-30",
                "end_date": "2026-10-01",
            },
            format="json",
        )
        assert reponse.status_code == 400

    def test_enseignant_ne_peut_pas_ouvrir_une_annee(
        self, api_teacher, annee_garnie
    ) -> None:
        reponse = api_teacher.post(
            reverse("year-dupliquer", args=[annee_garnie.id]),
            {
                "label": "2026-2027",
                "start_date": "2026-10-01",
                "end_date": "2027-06-30",
            },
            format="json",
        )
        assert reponse.status_code == 403


@pytest.mark.django_db
class TestReinscription:
    @pytest.fixture
    def annee_suivante(self, db) -> AcademicYear:
        from datetime import date

        return AcademicYear.objects.create(
            label="2026-2027",
            start_date=date(2026, 10, 1),
            end_date=date(2027, 6, 30),
        )

    def test_reinscription_en_lot(
        self, api_admin, student, annee_suivante, section_b
    ) -> None:
        autre = Student.objects.create(matricule="24099", full_name_ar="طالبة أخرى")

        reponse = api_admin.post(
            reverse("enrollment-reinscrire"),
            {
                "year": annee_suivante.id,
                "section": section_b.id,
                "students": [student.id, autre.id],
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["inscrites"] == 2
        assert Enrollment.objects.filter(year=annee_suivante).count() == 2

    def test_la_section_de_destination_est_celle_choisie(
        self, api_admin, student, enrollment, annee_suivante, section_b
    ) -> None:
        """L'étudiante était en المربيات ; l'administration la place ailleurs."""
        api_admin.post(
            reverse("enrollment-reinscrire"),
            {
                "year": annee_suivante.id,
                "section": section_b.id,
                "students": [student.id],
            },
            format="json",
        )
        nouvelle = Enrollment.objects.get(student=student, year=annee_suivante)
        assert nouvelle.section == section_b
        # L'inscription de l'année précédente n'a pas bougé.
        enrollment.refresh_from_db()
        assert enrollment.section.code == "SEC-A"

    def test_idempotence(self, api_admin, student, annee_suivante, section_b) -> None:
        charge = {
            "year": annee_suivante.id,
            "section": section_b.id,
            "students": [student.id],
        }
        api_admin.post(reverse("enrollment-reinscrire"), charge, format="json")
        reponse = api_admin.post(
            reverse("enrollment-reinscrire"), charge, format="json"
        )
        assert reponse.status_code == 200
        assert reponse.data["inscrites"] == 0
        assert len(reponse.data["deja_inscrites"]) == 1
        assert Enrollment.objects.filter(year=annee_suivante).count() == 1

    def test_etudiante_inconnue_signalee(
        self, api_admin, student, annee_suivante, section_b
    ) -> None:
        reponse = api_admin.post(
            reverse("enrollment-reinscrire"),
            {
                "year": annee_suivante.id,
                "section": section_b.id,
                "students": [student.id, 999_999],
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["inscrites"] == 1
        assert reponse.data["introuvables"] == [999_999]

    def test_liste_vide_refusee(
        self, api_admin, annee_suivante, section_b
    ) -> None:
        reponse = api_admin.post(
            reverse("enrollment-reinscrire"),
            {"year": annee_suivante.id, "section": section_b.id, "students": []},
            format="json",
        )
        assert reponse.status_code == 400

    def test_enseignant_ne_peut_pas_reinscrire(
        self, api_teacher, student, annee_suivante, section_b
    ) -> None:
        reponse = api_teacher.post(
            reverse("enrollment-reinscrire"),
            {
                "year": annee_suivante.id,
                "section": section_b.id,
                "students": [student.id],
            },
            format="json",
        )
        assert reponse.status_code == 403
