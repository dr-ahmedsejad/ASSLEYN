"""Tests de la vue d'avancement de la saisie."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.academics.models import ExamSession, SemesterState
from apps.grading.models import Grade, GradeStatus
from apps.results.services import recompute_semester

URL = reverse("grade-avancement")


@pytest.mark.django_db
class TestAvancement:
    def test_matieres_non_commencees(
        self,
        api_admin,
        fasl1,
        curriculum_a_quran,
        curriculum_a_fiqh,
        enrollment,
        autre_enrollment,
        rule,
    ) -> None:
        reponse = api_admin.get(URL, {"semester": fasl1.id})
        assert reponse.status_code == 200
        assert reponse.data["total"] == {"attendues": 4, "saisies": 0}

        section = reponse.data["sections"][0]
        assert section["effectif"] == 2
        assert len(section["matieres"]) == 2
        assert {m["statut"] for m in section["matieres"]} == {"NON_COMMENCEE"}

    def test_matiere_partielle_puis_complete(
        self,
        api_admin,
        fasl1,
        curriculum_a_quran,
        enrollment,
        autre_enrollment,
        rule,
        admin_user,
    ) -> None:
        Grade.objects.create(
            enrollment=enrollment,
            curriculum=curriculum_a_quran,
            value=Decimal("15"),
            status=GradeStatus.ENTERED,
            entered_by=admin_user,
        )
        matiere = self._matiere(api_admin, fasl1, curriculum_a_quran.id)
        assert matiere["saisies"] == 1
        assert matiere["attendues"] == 2
        assert matiere["statut"] == "PARTIELLE"

        Grade.objects.create(
            enrollment=autre_enrollment,
            curriculum=curriculum_a_quran,
            value=None,
            status=GradeStatus.ABSENT,
            entered_by=admin_user,
        )
        matiere = self._matiere(api_admin, fasl1, curriculum_a_quran.id)
        # Une absence est une decision : la matiere est bien terminee.
        assert matiere["saisies"] == 2
        assert matiere["statut"] == "COMPLETE"

    def test_enseignant_ne_voit_que_ses_matieres(
        self,
        api_teacher,
        fasl1,
        curriculum_a_quran,
        curriculum_a_fiqh,
        enrollment,
        rule,
    ) -> None:
        reponse = api_teacher.get(URL, {"semester": fasl1.id})
        matieres = [
            m for s in reponse.data["sections"] for m in s["matieres"]
        ]
        assert [m["curriculum"] for m in matieres] == [curriculum_a_quran.id]

    def test_rattrapage_ne_compte_que_les_convoquees(
        self,
        api_admin,
        fasl1,
        section_a,
        curriculum_a_quran,
        enrollment,
        autre_enrollment,
        rule,
        admin_user,
    ) -> None:
        Grade.objects.create(
            enrollment=enrollment,
            curriculum=curriculum_a_quran,
            value=Decimal("16"),
            status=GradeStatus.ENTERED,
            entered_by=admin_user,
        )
        Grade.objects.create(
            enrollment=autre_enrollment,
            curriculum=curriculum_a_quran,
            value=Decimal("6"),
            status=GradeStatus.ENTERED,
            entered_by=admin_user,
        )
        recompute_semester(fasl1, section_a, ExamSession.NORMAL)

        reponse = api_admin.get(
            URL, {"semester": fasl1.id, "session": ExamSession.RESIT}
        )
        matiere = reponse.data["sections"][0]["matieres"][0]
        # Une seule etudiante est convoquee, pas les deux.
        assert matiere["attendues"] == 1
        assert matiere["saisies"] == 0
        assert reponse.data["semester"]["session"] == ExamSession.RESIT

    def test_etat_du_fasl_est_rapporte(
        self, api_admin, fasl1, curriculum_a_quran, enrollment, rule
    ) -> None:
        reponse = api_admin.get(URL, {"semester": fasl1.id})
        assert reponse.data["semester"]["editable"] is True

        fasl1.state = SemesterState.CLOSED
        fasl1.save(update_fields=["state"])
        reponse = api_admin.get(URL, {"semester": fasl1.id})
        assert reponse.data["semester"]["editable"] is False

    def test_fasl_sans_programme(self, api_admin, fasl2, rule) -> None:
        reponse = api_admin.get(URL, {"semester": fasl2.id})
        assert reponse.data["sections"] == []
        assert reponse.data["total"]["attendues"] == 0

    def test_parametre_manquant(self, api_admin) -> None:
        assert api_admin.get(URL).status_code == 400

    def test_fasl_inconnu(self, api_admin) -> None:
        assert api_admin.get(URL, {"semester": 999_999}).status_code == 400

    def test_session_inconnue(self, api_admin, fasl1, rule) -> None:
        reponse = api_admin.get(URL, {"semester": fasl1.id, "session": "XYZ"})
        assert reponse.status_code == 400

    def test_etudiante_refusee(self, api_student, fasl1, rule) -> None:
        assert api_student.get(URL, {"semester": fasl1.id}).status_code == 403

    def _matiere(self, client, fasl, curriculum_id: int) -> dict:
        reponse = client.get(URL, {"semester": fasl.id})
        for section in reponse.data["sections"]:
            for matiere in section["matieres"]:
                if matiere["curriculum"] == curriculum_id:
                    return matiere
        raise AssertionError("matiere absente de l'avancement")
