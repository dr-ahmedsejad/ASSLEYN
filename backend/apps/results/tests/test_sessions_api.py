"""
Parcours complet des deux sessions d'un فصل.

Session normale → clôture → délibération (seuil par قسم) → publication →
ouverture du rattrapage → saisie restreinte aux convoquées → résultat final.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.academics.models import ExamSession, SemesterState
from apps.grading.models import Grade, GradeStatus, GradingRule
from apps.results.models import SemesterResult, SubjectResult
from apps.results.services import recompute_semester, resit_candidates, retained_results

SHEET = reverse("grade-sheet")
BULK = reverse("grade-sheet-bulk")


@pytest.fixture
def cohorte(
    curriculum_a_quran, enrollment, autre_enrollment, fasl1, section_a, rule, admin_user
):
    """
    Deux etudiantes sur une seule matiere (coefficient 5) :
    - 24001 : 16 → ناجحة
    - 24002 : 6  → استدراك, matiere غير مستوفي
    """
    Grade.objects.create(
        enrollment=enrollment,
        curriculum=curriculum_a_quran,
        value=Decimal("16"),
        status=GradeStatus.ENTERED,
        session=ExamSession.NORMAL,
        entered_by=admin_user,
    )
    Grade.objects.create(
        enrollment=autre_enrollment,
        curriculum=curriculum_a_quran,
        value=Decimal("6"),
        status=GradeStatus.ENTERED,
        session=ExamSession.NORMAL,
        entered_by=admin_user,
    )
    recompute_semester(fasl1, section_a, ExamSession.NORMAL)
    return {"reussie": enrollment, "sessionnaire": autre_enrollment}


def publier(fasl1) -> None:
    fasl1.state = SemesterState.PUBLISHED
    fasl1.save(update_fields=["state"])


@pytest.mark.django_db
class TestOuvertureDuRattrapage:
    def test_refuse_avant_publication(self, api_admin, fasl1, rule) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(f"{url}open-resit/")
        assert reponse.status_code == 400
        fasl1.refresh_from_db()
        assert fasl1.current_session == ExamSession.NORMAL

    def test_ouverture_apres_publication(self, api_admin, fasl1, cohorte) -> None:
        publier(fasl1)
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(f"{url}open-resit/")
        assert reponse.status_code == 200

        fasl1.refresh_from_db()
        assert fasl1.current_session == ExamSession.RESIT
        assert fasl1.state == SemesterState.OPEN

    def test_deuxieme_ouverture_refusee(self, api_admin, fasl1, cohorte) -> None:
        publier(fasl1)
        url = reverse("semester-detail", args=[fasl1.id])
        api_admin.post(f"{url}open-resit/")
        assert api_admin.post(f"{url}open-resit/").status_code == 400

    def test_enseignant_ne_peut_pas_ouvrir(self, api_teacher, fasl1, cohorte) -> None:
        publier(fasl1)
        url = reverse("semester-detail", args=[fasl1.id])
        assert api_teacher.post(f"{url}open-resit/").status_code == 403


@pytest.mark.django_db
class TestConvocation:
    def test_seules_les_matieres_non_satisfaites_sont_convoquees(
        self, fasl1, curriculum_a_quran, cohorte
    ) -> None:
        convoquees = resit_candidates(fasl1, curriculum_a_quran)
        assert convoquees == {cohorte["sessionnaire"].id}

    def test_la_grille_de_rattrapage_ne_montre_que_les_convoquees(
        self, api_teacher, fasl1, curriculum_a_quran, cohorte
    ) -> None:
        publier(fasl1)
        api_teacher.get(SHEET)  # bruit : sans parametre
        fasl1.current_session = ExamSession.RESIT
        fasl1.state = SemesterState.OPEN
        fasl1.save(update_fields=["current_session", "state"])

        reponse = api_teacher.get(SHEET, {"curriculum": curriculum_a_quran.id})
        assert reponse.status_code == 200
        assert reponse.data["session"] == ExamSession.RESIT
        assert len(reponse.data["rows"]) == 1
        ligne = reponse.data["rows"][0]
        assert ligne["matricule"] == "24002"
        # La note de la session normale est rappelee a l'enseignant.
        assert ligne["normal_value"] == "6.00"
        assert ligne["value"] is None

    def test_la_grille_normale_montre_tout_le_monde(
        self, api_teacher, curriculum_a_quran, cohorte
    ) -> None:
        reponse = api_teacher.get(
            SHEET, {"curriculum": curriculum_a_quran.id, "session": "NORMAL"}
        )
        assert len(reponse.data["rows"]) == 2
        assert reponse.data["rows"][0]["normal_value"] is None


@pytest.mark.django_db
class TestSaisieDuRattrapage:
    @pytest.fixture(autouse=True)
    def _rattrapage_ouvert(self, fasl1, cohorte):
        publier(fasl1)
        fasl1.current_session = ExamSession.RESIT
        fasl1.state = SemesterState.OPEN
        fasl1.save(update_fields=["current_session", "state"])

    def test_la_meilleure_note_est_retenue(
        self, api_teacher, curriculum_a_quran, fasl1, cohorte
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [
                    {"enrollment": cohorte["sessionnaire"].id, "value": "11.00"}
                ],
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["session"] == ExamSession.RESIT

        # La note de la session normale n'a pas bouge.
        assert (
            Grade.objects.get(
                enrollment=cohorte["sessionnaire"], session=ExamSession.NORMAL
            ).value
            == Decimal("6.00")
        )

        resultat = SemesterResult.objects.get(
            enrollment=cohorte["sessionnaire"],
            semester=fasl1,
            session=ExamSession.RESIT,
        )
        assert resultat.average == Decimal("11")
        assert resultat.decision_computed == "PASSED"

        detail = SubjectResult.objects.get(semester_result=resultat)
        assert detail.normal_value == Decimal("6.00")
        assert detail.resit_value == Decimal("11.00")
        assert detail.value == Decimal("11.00")

    def test_un_rattrapage_plus_faible_ne_penalise_pas(
        self, api_teacher, curriculum_a_quran, fasl1, cohorte
    ) -> None:
        api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": cohorte["sessionnaire"].id, "value": "3.00"}],
            },
            format="json",
        )
        resultat = SemesterResult.objects.get(
            enrollment=cohorte["sessionnaire"], session=ExamSession.RESIT
        )
        assert resultat.average == Decimal("6")

    def test_une_etudiante_non_convoquee_est_refusee(
        self, api_teacher, curriculum_a_quran, cohorte
    ) -> None:
        reponse = api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": cohorte["reussie"].id, "value": "19.00"}],
            },
            format="json",
        )
        assert reponse.status_code == 400
        assert not Grade.objects.filter(session=ExamSession.RESIT).exists()

    def test_le_resultat_de_la_session_normale_survit(
        self, api_teacher, curriculum_a_quran, fasl1, cohorte
    ) -> None:
        api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": cohorte["sessionnaire"].id, "value": "11.00"}],
            },
            format="json",
        )
        normal = SemesterResult.objects.get(
            enrollment=cohorte["sessionnaire"], session=ExamSession.NORMAL
        )
        assert normal.average == Decimal("6")
        assert normal.decision_computed == "RESIT"

    def test_resultat_retenu_privilegie_le_rattrapage(
        self, api_teacher, curriculum_a_quran, fasl1, cohorte
    ) -> None:
        api_teacher.post(
            BULK,
            {
                "curriculum": curriculum_a_quran.id,
                "grades": [{"enrollment": cohorte["sessionnaire"].id, "value": "11.00"}],
            },
            format="json",
        )
        retenus = retained_results(fasl1, list(cohorte.values()))
        assert retenus[cohorte["sessionnaire"].id].session == ExamSession.RESIT
        assert retenus[cohorte["reussie"].id].session == ExamSession.RESIT


@pytest.mark.django_db
class TestSeuilParSection:
    def test_abaisser_le_seuil_fait_reussir(
        self, api_admin, fasl1, section_a, cohorte
    ) -> None:
        """Barre à 6 : l'étudiante à 6/20 devient ناجحة."""
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(
            f"{url}seuil/",
            {
                "section": section_a.id,
                "pass_threshold": "6.00",
                "note": "قرار مجلس القسم",
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["pass_threshold"] == "6.00"

        resultat = SemesterResult.objects.get(
            enrollment=cohorte["sessionnaire"], session=ExamSession.NORMAL
        )
        assert resultat.decision_computed == "PASSED"

    def test_une_nouvelle_version_de_regle_est_creee(
        self, api_admin, fasl1, section_a, cohorte
    ) -> None:
        """L'ancienne règle survit : les bulletins déjà émis restent explicables."""
        url = reverse("semester-detail", args=[fasl1.id])
        api_admin.post(
            f"{url}seuil/",
            {"section": section_a.id, "pass_threshold": "9.00", "note": "مداولة"},
            format="json",
        )
        regle = GradingRule.objects.get(section=section_a, semester=fasl1)
        assert regle.version == 1
        assert regle.created_by.username == "admin"
        assert regle.note == "مداولة"
        # La regle generale de l'annee est intacte.
        assert GradingRule.objects.get(
            section__isnull=True, semester__isnull=True
        ).pass_threshold == Decimal("10")

    def test_le_seuil_ne_deborde_pas_sur_une_autre_section(
        self, api_admin, fasl1, section_a, section_b, cohorte, year
    ) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        api_admin.post(
            f"{url}seuil/",
            {"section": section_a.id, "pass_threshold": "6.00", "note": "مداولة"},
            format="json",
        )
        from apps.results.services import resolve_rule

        assert resolve_rule(year, section_a, fasl1).pass_threshold == Decimal("6.00")
        assert resolve_rule(year, section_b, fasl1).pass_threshold == Decimal("10")

    def test_fixer_les_deux_seuils(
        self, api_admin, fasl1, section_a, cohorte, year
    ) -> None:
        """La commission arrête la barre et le plancher pour ce قسم."""
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(
            f"{url}seuil/",
            {
                "section": section_a.id,
                "pass_threshold": "12.00",
                "compensation_floor": "8.00",
                "note": "قرار المجلس",
            },
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["pass_threshold"] == "12.00"
        assert reponse.data["compensation_floor"] == "8.00"

        from apps.results.services import resolve_rule

        regle = resolve_rule(year, section_a, fasl1)
        assert regle.pass_threshold == Decimal("12.00")
        assert regle.compensation_floor == Decimal("8.00")

    def test_plancher_au_dessus_de_la_barre_refuse(
        self, api_admin, fasl1, section_a, cohorte
    ) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(
            f"{url}seuil/",
            {
                "section": section_a.id,
                "pass_threshold": "9.00",
                "compensation_floor": "11.00",
                "note": "مداولة",
            },
            format="json",
        )
        assert reponse.status_code == 400
        assert "compensation_floor" in reponse.data

    def test_plancher_negatif_refuse(
        self, api_admin, fasl1, section_a, cohorte
    ) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(
            f"{url}seuil/",
            {
                "section": section_a.id,
                "pass_threshold": "10.00",
                "compensation_floor": "-1.00",
            },
            format="json",
        )
        assert reponse.status_code == 400

    def test_plancher_omis_reste_inchange(
        self, api_admin, fasl1, section_a, cohorte, year
    ) -> None:
        """Sans indication, le plancher garde sa valeur."""
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(
            f"{url}seuil/",
            {"section": section_a.id, "pass_threshold": "12.00"},
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["compensation_floor"] == "7.00"

    def test_le_plancher_ne_depasse_jamais_la_barre(
        self, api_admin, fasl1, section_a, cohorte, year
    ) -> None:
        """Descendre la barre sous le plancher aligne celui-ci, sans refus."""
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(
            f"{url}seuil/",
            {"section": section_a.id, "pass_threshold": "6.00"},
            format="json",
        )
        assert reponse.status_code == 200
        assert reponse.data["compensation_floor"] == "6.00"

    def test_le_plancher_change_les_decisions_par_matiere(
        self, api_admin, fasl1, section_a, cohorte, curriculum_a_quran
    ) -> None:
        """Une note de 6 est éliminatoire à 7, compensable à 5."""
        from apps.results.models import SubjectResult

        detail = SubjectResult.objects.get(
            semester_result__enrollment=cohorte["sessionnaire"],
            semester_result__session=ExamSession.NORMAL,
            curriculum=curriculum_a_quran,
        )
        assert detail.decision == "NOT_SATISFIED"

        url = reverse("semester-detail", args=[fasl1.id])
        api_admin.post(
            f"{url}seuil/",
            {
                "section": section_a.id,
                "pass_threshold": "6.00",
                "compensation_floor": "5.00",
                "note": "مداولة",
            },
            format="json",
        )
        detail.refresh_from_db()
        assert detail.decision == "SATISFIED"

    def test_refuse_apres_publication(
        self, api_admin, fasl1, section_a, cohorte
    ) -> None:
        publier(fasl1)
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_admin.post(
            f"{url}seuil/",
            {"section": section_a.id, "pass_threshold": "6.00", "note": "مداولة"},
            format="json",
        )
        assert reponse.status_code == 400

    def test_enseignant_ne_peut_pas_fixer_le_seuil(
        self, api_teacher, fasl1, section_a, cohorte
    ) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        reponse = api_teacher.post(
            f"{url}seuil/",
            {"section": section_a.id, "pass_threshold": "6.00", "note": "مداولة"},
            format="json",
        )
        assert reponse.status_code == 403

    def test_lecture_des_seuils_en_vigueur(
        self, api_admin, fasl1, section_a, cohorte
    ) -> None:
        url = reverse("semester-detail", args=[fasl1.id])
        api_admin.post(
            f"{url}seuil/",
            {"section": section_a.id, "pass_threshold": "8.50", "note": "مداولة"},
            format="json",
        )
        reponse = api_admin.get(f"{url}seuils/")
        assert reponse.status_code == 200
        ligne = next(r for r in reponse.data if r["section"] == section_a.id)
        assert ligne["pass_threshold"] == "8.50"
        assert ligne["propre_au_fasl"] is True
