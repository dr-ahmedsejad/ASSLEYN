"""
Tests de la grille de saisie.

Ce que l'on verifie ici est autant fonctionnel que securitaire : un enseignant
ne doit pouvoir ecrire que dans sa matiere, et seulement pendant que le فصل
est ouvert.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.academics.models import SemesterState
from apps.grading.models import Grade, GradeHistory, GradeStatus
from apps.results.models import SemesterResult

SHEET = reverse("grade-sheet")
BULK = reverse("grade-sheet-bulk")


@pytest.mark.django_db
class TestLectureDeLaGrille:
    def test_enseignant_affecte_voit_sa_grille(
        self, api_teacher, curriculum_a_quran, enrollment, autre_enrollment, rule
    ) -> None:
        reponse = api_teacher.get(SHEET, {"curriculum": curriculum_a_quran.id})
        assert reponse.status_code == 200
        assert reponse.data["curriculum"]["subject_name"] == "القرآن الكريم"
        assert reponse.data["curriculum"]["editable"] is True
        assert len(reponse.data["rows"]) == 2
        assert reponse.data["completion"] == {"saisies": 0, "total": 2}
        assert all(r["status"] == GradeStatus.MISSING for r in reponse.data["rows"])

    def test_enseignant_non_affecte_refuse(
        self, api_teacher, curriculum_a_fiqh, enrollment, rule
    ) -> None:
        """الفقه n'est pas sa matiere, meme dans sa section."""
        reponse = api_teacher.get(SHEET, {"curriculum": curriculum_a_fiqh.id})
        assert reponse.status_code == 403

    def test_autre_section_refusee(
        self, api_teacher, curriculum_b_quran, enrollment_section_b, rule
    ) -> None:
        reponse = api_teacher.get(SHEET, {"curriculum": curriculum_b_quran.id})
        assert reponse.status_code == 403

    def test_etudiante_refusee(self, api_student, curriculum_a_quran, rule) -> None:
        assert (
            api_student.get(SHEET, {"curriculum": curriculum_a_quran.id}).status_code
            == 403
        )

    def test_admin_voit_toutes_les_grilles(
        self, api_admin, curriculum_a_fiqh, enrollment, rule
    ) -> None:
        assert (
            api_admin.get(SHEET, {"curriculum": curriculum_a_fiqh.id}).status_code == 200
        )

    def test_grille_ne_contient_que_la_section_de_la_matiere(
        self,
        api_admin,
        curriculum_a_quran,
        enrollment,
        enrollment_section_b,
        rule,
    ) -> None:
        reponse = api_admin.get(SHEET, {"curriculum": curriculum_a_quran.id})
        matricules = {r["matricule"] for r in reponse.data["rows"]}
        assert matricules == {"24001"}


@pytest.mark.django_db
class TestEcritureDesNotes:
    def test_enregistrement_et_recalcul(
        self, api_teacher, curriculum_a_quran, enrollment, autre_enrollment, rule
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [
                    {"enrollment": enrollment.id, "value": "17.50"},
                    {"enrollment": autre_enrollment.id, "value": "12.00"},
                ],
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["modifiees"] == 2
        assert Grade.objects.count() == 2
        # Le recalcul s'est declenche tout seul : c'est l'automatisme attendu.
        assert SemesterResult.objects.count() == 2
        premiere = SemesterResult.objects.get(enrollment=enrollment)
        assert premiere.average == Decimal("17.5")
        assert premiere.rank == 1

    def test_chaque_ecriture_est_journalisee(
        self, api_teacher, curriculum_a_quran, enrollment, rule
    ) -> None:
        payload = {
            "curriculum": curriculum_a_quran.id,
            "grades": [{"enrollment": enrollment.id, "value": "10.00"}],
        }
        api_teacher.post(BULK, payload, format="json")
        payload["grades"][0]["value"] = "14.00"
        payload["grades"][0]["reason"] = "تصحيح خطأ في النقل"
        api_teacher.post(BULK, payload, format="json")

        historique = GradeHistory.objects.order_by("changed_at")
        assert historique.count() == 2
        assert historique[0].old_value is None
        assert historique[1].old_value == Decimal("10.00")
        assert historique[1].new_value == Decimal("14.00")
        assert historique[1].reason == "تصحيح خطأ في النقل"
        assert historique[1].changed_by.username == "prof"

    def test_absence_enregistree_sans_valeur(
        self, api_teacher, curriculum_a_quran, enrollment, rule
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [
                    {
                        "enrollment": enrollment.id,
                        "value": None,
                        "status": GradeStatus.ABSENT,
                    }
                ],
            },
            format="json",
        )
        assert reponse.status_code == 200
        note = Grade.objects.get()
        assert note.status == GradeStatus.ABSENT
        assert note.value is None

    def test_note_hors_bareme_refusee(
        self, api_teacher, curriculum_a_quran, enrollment, rule
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": enrollment.id, "value": "21.00"}],
            },
            format="json",
        )
        assert reponse.status_code == 400
        assert Grade.objects.count() == 0

    def test_valeur_sans_statut_coherent_refusee(
        self, api_teacher, curriculum_a_quran, enrollment, rule
    ) -> None:
        """Une note chiffree avec un statut « غائبة » n'a pas de sens."""
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [
                    {
                        "enrollment": enrollment.id,
                        "value": "12.00",
                        "status": GradeStatus.ABSENT,
                    }
                ],
            },
            format="json",
        )
        assert reponse.status_code == 400

    def test_une_ligne_invalide_annule_tout_le_lot(
        self, api_teacher, curriculum_a_quran, enrollment, autre_enrollment, rule
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [
                    {"enrollment": enrollment.id, "value": "15.00"},
                    {"enrollment": autre_enrollment.id, "value": "99.00"},
                ],
            },
            format="json",
        )
        assert reponse.status_code == 400
        assert Grade.objects.count() == 0

    def test_etudiante_d_une_autre_section_refusee(
        self, api_teacher, curriculum_a_quran, enrollment_section_b, rule
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": enrollment_section_b.id, "value": "15.00"}],
            },
            format="json",
        )
        assert reponse.status_code == 400
        assert Grade.objects.count() == 0

    def test_enseignant_non_affecte_ne_peut_pas_ecrire(
        self, api_teacher, curriculum_a_fiqh, enrollment, rule
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_fiqh.id,
                "grades": [{"enrollment": enrollment.id, "value": "15.00"}],
            },
            format="json",
        )
        assert reponse.status_code == 403
        assert Grade.objects.count() == 0

    def test_etudiante_ne_peut_pas_ecrire(
        self, api_student, curriculum_a_quran, enrollment, rule
    ) -> None:
        reponse = api_student.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": enrollment.id, "value": "20.00"}],
            },
            format="json",
        )
        assert reponse.status_code == 403
        assert Grade.objects.count() == 0

    def test_doublon_dans_le_lot_refuse(
        self, api_teacher, curriculum_a_quran, enrollment, rule
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [
                    {"enrollment": enrollment.id, "value": "15.00"},
                    {"enrollment": enrollment.id, "value": "16.00"},
                ],
            },
            format="json",
        )
        assert reponse.status_code == 400

    def test_reenregistrer_la_meme_valeur_ne_cree_pas_d_historique(
        self, api_teacher, curriculum_a_quran, enrollment, rule
    ) -> None:
        payload = {
            "curriculum": curriculum_a_quran.id,
            "grades": [{"enrollment": enrollment.id, "value": "15.00"}],
        }
        api_teacher.post(BULK, payload, format="json")
        reponse = api_teacher.post(BULK, payload, format="json")
        assert reponse.data["modifiees"] == 0
        assert GradeHistory.objects.count() == 1


@pytest.mark.django_db
class TestCycleDeVieDuFasl:
    @pytest.mark.parametrize(
        "etat", [SemesterState.DRAFT, SemesterState.CLOSED, SemesterState.PUBLISHED]
    )
    def test_ecriture_refusee_hors_saisie_ouverte(
        self, api_teacher, curriculum_a_quran, enrollment, fasl1, rule, etat
    ) -> None:
        fasl1.state = etat
        fasl1.save(update_fields=["state"])

        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": enrollment.id, "value": "15.00"}],
            },
            format="json",
        )
        assert reponse.status_code == 400
        assert Grade.objects.count() == 0

    def test_lecture_reste_possible_apres_cloture(
        self, api_teacher, curriculum_a_quran, enrollment, fasl1, rule
    ) -> None:
        fasl1.state = SemesterState.CLOSED
        fasl1.save(update_fields=["state"])
        reponse = api_teacher.get(SHEET, {"curriculum": curriculum_a_quran.id})
        assert reponse.status_code == 200
        assert reponse.data["curriculum"]["editable"] is False

    def test_transitions_admin(self, api_admin, fasl1, rule) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        assert api_admin.post(f"{url}close/").status_code == 200
        assert api_admin.post(f"{url}publish/").status_code == 200
        fasl1.refresh_from_db()
        assert fasl1.state == SemesterState.PUBLISHED
        assert fasl1.published_at is not None

    def test_transition_interdite_refusee(self, api_admin, fasl1, rule) -> None:
        """Un فصل ouvert ne peut pas etre publie directement."""
        url = reverse("semester-detail", args=[fasl1.id])
        assert api_admin.post(f"{url}publish/").status_code == 400

    def test_enseignant_ne_peut_pas_changer_l_etat(self, api_teacher, fasl1) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        assert api_teacher.post(f"{url}close/").status_code == 403
