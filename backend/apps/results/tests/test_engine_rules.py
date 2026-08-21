"""Tests unitaires des regles du moteur, cas par cas."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.results.engine import (
    AbsencePolicy,
    AnnualInput,
    OverallDecision,
    RankingMode,
    Rules,
    SemesterAverage,
    StudentInput,
    SubjectDecision,
    SubjectGrade,
    compute_annual,
    compute_semester,
    compute_student,
    round_for_display,
)

D = Decimal


def eleve(cle: str, *notes: tuple[str, int, float | None]) -> StudentInput:
    return StudentInput(
        student_key=cle,
        grades=tuple(
            SubjectGrade(code, D(coef), None if val is None else D(str(val)))
            for code, coef, val in notes
        ),
    )


class TestMoyenne:
    def test_moyenne_ponderee(self) -> None:
        # Cas reel : النياه محمد, المربيات — (18.75*5 + 18.5*3 + 16*2 + 17.5*4) / 14
        result = compute_student(
            eleve("a", ("NAHW", 4, 17.5), ("LUGHA", 2, 16), ("FIQH", 3, 18.5), ("QURAN", 5, 18.75)),
            Rules(),
        )
        assert result.average == D("17.9464285714")
        assert result.total_coefficient == D("14")

    def test_coefficient_nul_refuse(self) -> None:
        with pytest.raises(ValueError, match="Coefficient invalide"):
            SubjectGrade("NAHW", D("0"), D("12"))

    def test_note_negative_refusee(self) -> None:
        with pytest.raises(ValueError, match="Note negative"):
            SubjectGrade("NAHW", D("4"), D("-1"))


class TestCompensation:
    def test_note_sous_le_seuil_rattrapee_par_la_moyenne(self) -> None:
        """8/20 avec une moyenne de 15 : la matiere est مستوفي."""
        result = compute_student(
            eleve("a", ("FIQH", 1, 8), ("QURAN", 3, 17.5)), Rules()
        )
        assert result.average >= D("10")
        assert result.subjects[0].decision is SubjectDecision.SATISFIED

    def test_note_sous_le_plancher_jamais_rattrapee(self) -> None:
        """6.5/20 est sous le plancher de 7 : aucune moyenne ne la sauve."""
        result = compute_student(
            eleve("a", ("FIQH", 1, 6.5), ("QURAN", 9, 20)), Rules()
        )
        assert result.average > D("18")
        assert result.subjects[0].decision is SubjectDecision.NOT_SATISFIED
        assert result.decision is OverallDecision.RESIT

    def test_pas_de_compensation_si_moyenne_insuffisante(self) -> None:
        result = compute_student(
            eleve("a", ("FIQH", 1, 8), ("QURAN", 1, 9)), Rules()
        )
        assert result.average < D("10")
        assert result.subjects[0].decision is SubjectDecision.NOT_SATISFIED

    def test_note_au_dessus_du_seuil_toujours_satisfaite(self) -> None:
        """12/20 reste مستوفي meme si la moyenne generale est mauvaise."""
        result = compute_student(
            eleve("a", ("FIQH", 1, 12), ("QURAN", 9, 2)), Rules()
        )
        assert result.average < D("10")
        assert result.subjects[0].decision is SubjectDecision.SATISFIED


class TestDecisionGlobale:
    def test_reussite(self) -> None:
        result = compute_student(eleve("a", ("A", 1, 12), ("B", 1, 14)), Rules())
        assert result.decision is OverallDecision.PASSED

    def test_moyenne_juste_sous_le_seuil(self) -> None:
        result = compute_student(eleve("a", ("A", 1, D("9.99")), ("B", 1, 10)), Rules())
        assert result.decision is OverallDecision.RESIT

    def test_moyenne_suffisante_mais_une_note_sous_le_plancher(self) -> None:
        result = compute_student(eleve("a", ("A", 1, 6), ("B", 9, 20)), Rules())
        assert result.average > D("18")
        assert result.decision is OverallDecision.RESIT


class TestAbsences:
    def test_absence_comptee_zero(self) -> None:
        result = compute_student(
            eleve("a", ("A", 1, None), ("B", 1, 20)),
            Rules(absence_policy=AbsencePolicy.COUNT_AS_ZERO),
        )
        assert result.average == D("10")
        assert result.subjects[0].effective_value == D("0")
        assert result.subjects[0].decision is SubjectDecision.NOT_SATISFIED

    def test_absence_exclue_du_calcul(self) -> None:
        """Le coefficient de la matiere absente sort aussi du denominateur."""
        result = compute_student(
            eleve("a", ("A", 1, None), ("B", 1, 20)),
            Rules(absence_policy=AbsencePolicy.EXCLUDE),
        )
        assert result.average == D("20")
        assert result.total_coefficient == D("1")
        assert result.subjects[0].decision is SubjectDecision.NOT_APPLICABLE

    def test_etudiante_sans_aucune_note_comptee(self) -> None:
        result = compute_student(
            eleve("a", ("A", 1, None)),
            Rules(absence_policy=AbsencePolicy.EXCLUDE),
        )
        assert result.average == D("0")
        assert result.has_no_counted_subject is True
        assert result.decision is OverallDecision.RESIT

    def test_dispense_retire_la_matiere(self) -> None:
        etudiante = StudentInput(
            "a",
            (
                SubjectGrade("A", D("3"), None, counts=False),
                SubjectGrade("B", D("5"), D("16")),
            ),
        )
        result = compute_student(etudiante, Rules())
        assert result.average == D("16")
        assert result.total_coefficient == D("5")


class TestClassement:
    def _moyennes(self, *valeurs: float) -> list[StudentInput]:
        return [eleve(f"e{i}", ("A", 1, v)) for i, v in enumerate(valeurs)]

    def test_rang_dense(self) -> None:
        """Convention de l'institut : 1, 2, 3, 3, 4."""
        rangs = [r.rank for r in compute_semester(self._moyennes(18, 16, 15, 15, 14))]
        assert rangs == [1, 2, 3, 3, 4]

    def test_rang_standard(self) -> None:
        rangs = [
            r.rank
            for r in compute_semester(
                self._moyennes(18, 16, 15, 15, 14),
                Rules(ranking_mode=RankingMode.STANDARD),
            )
        ]
        assert rangs == [1, 2, 3, 3, 5]

    def test_resultats_rendus_dans_l_ordre_du_classement(self) -> None:
        results = compute_semester(self._moyennes(12, 18, 15))
        assert [r.average for r in results] == [D("18"), D("15"), D("12")]

    def test_toutes_a_zero_partagent_le_premier_rang(self) -> None:
        """Cas reel : les etudiantes non presentees sont toutes a egalite."""
        rangs = [r.rank for r in compute_semester(self._moyennes(0, 0, 0))]
        assert rangs == [1, 1, 1]


class TestAnnuel:
    def test_moyenne_arithmetique_des_deux_fasl(self) -> None:
        annuel = compute_annual(
            [
                AnnualInput(
                    "a",
                    (
                        SemesterAverage(1, D("12")),
                        SemesterAverage(2, D("16")),
                    ),
                )
            ]
        )
        assert annuel[0].average == D("14")
        assert annuel[0].decision is OverallDecision.PASSED

    def test_ponderation_inegale(self) -> None:
        annuel = compute_annual(
            [
                AnnualInput(
                    "a",
                    (
                        SemesterAverage(1, D("12"), D("1")),
                        SemesterAverage(2, D("16"), D("3")),
                    ),
                )
            ]
        )
        assert annuel[0].average == D("15")

    def test_dossier_incomplet_ne_peut_pas_reussir(self) -> None:
        annuel = compute_annual([AnnualInput("a", (SemesterAverage(1, D("18")),))])
        assert annuel[0].semester_count == 1
        assert annuel[0].decision is OverallDecision.RESIT

    def test_classement_annuel_dense(self) -> None:
        eleves = [
            AnnualInput(
                str(i), (SemesterAverage(1, D(str(m))), SemesterAverage(2, D(str(m))))
            )
            for i, m in enumerate([18, 15, 15, 12])
        ]
        assert [r.rank for r in compute_annual(eleves)] == [1, 2, 2, 3]


class TestReglement:
    def test_plancher_superieur_au_seuil_refuse(self) -> None:
        with pytest.raises(ValueError, match="plancher de compensation"):
            Rules(pass_threshold=D("10"), compensation_floor=D("12"))

    def test_seuil_superieur_a_la_note_max_refuse(self) -> None:
        with pytest.raises(ValueError, match="seuil de reussite"):
            Rules(max_grade=D("20"), pass_threshold=D("21"))

    def test_reglement_alternatif_sur_100(self) -> None:
        """Le moteur ne presuppose pas le bareme /20."""
        regles = Rules(
            max_grade=D("100"), pass_threshold=D("50"), compensation_floor=D("35")
        )
        result = compute_student(eleve("a", ("A", 1, 40), ("B", 1, 80)), regles)
        assert result.average == D("60")
        assert result.subjects[0].decision is SubjectDecision.SATISFIED
        assert result.decision is OverallDecision.PASSED


class TestAffichage:
    @pytest.mark.parametrize(
        ("brut", "attendu"),
        [
            ("17.9464285714", "17.95"),
            ("9.4285714286", "9.43"),
            ("10.005", "10.01"),
            ("0", "0.00"),
        ],
    )
    def test_arrondi_commercial(self, brut: str, attendu: str) -> None:
        assert round_for_display(D(brut)) == D(attendu)

    def test_l_arrondi_ne_change_jamais_la_decision(self) -> None:
        """9.999 s'affiche 10.00 mais reste un استدراك."""
        result = compute_student(
            eleve("a", ("A", 1, D("9.998")), ("B", 1, D("10"))), Rules()
        )
        assert round_for_display(result.average) == D("10.00")
        assert result.decision is OverallDecision.RESIT
