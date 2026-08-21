"""Tests unitaires de la regle de rattrapage."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.results.engine import (
    OverallDecision,
    ResitPolicy,
    Rules,
    StudentInput,
    SubjectDecision,
    SubjectGrade,
    compute_student,
    retained_value,
)

D = Decimal


def note(normale: float | None, rattrapage: float | None = None) -> SubjectGrade:
    return SubjectGrade(
        "A",
        D("1"),
        None if normale is None else D(str(normale)),
        resit_value=None if rattrapage is None else D(str(rattrapage)),
    )


class TestNoteRetenue:
    def test_sans_rattrapage_la_note_normale_est_retenue(self) -> None:
        assert retained_value(note(12), Rules()) == D("12")

    def test_meilleure_des_deux(self) -> None:
        """Regle de l'institut : on ne perd jamais de points en repassant."""
        regles = Rules(resit_policy=ResitPolicy.BEST)
        assert retained_value(note(8, 14), regles) == D("14")
        assert retained_value(note(14, 8), regles) == D("14")

    def test_absente_a_la_session_normale_puis_presente(self) -> None:
        assert retained_value(note(None, 11), Rules()) == D("11")

    def test_remplacement(self) -> None:
        regles = Rules(resit_policy=ResitPolicy.REPLACE)
        assert retained_value(note(14, 8), regles) == D("8")
        assert retained_value(note(8, 14), regles) == D("14")

    def test_plafonnee_au_seuil(self) -> None:
        """Le rattrapage ne fait pas mieux que la barre de reussite."""
        regles = Rules(resit_policy=ResitPolicy.BEST_CAPPED)
        assert retained_value(note(6, 18), regles) == D("10")

    def test_plafond_ne_degrade_pas_une_bonne_note_normale(self) -> None:
        regles = Rules(resit_policy=ResitPolicy.BEST_CAPPED)
        assert retained_value(note(15, 18), regles) == D("15")

    def test_note_de_rattrapage_negative_refusee(self) -> None:
        with pytest.raises(ValueError, match="Note de rattrapage negative"):
            SubjectGrade("A", D("1"), D("5"), resit_value=D("-1"))


class TestCalculApresRattrapage:
    def test_le_rattrapage_fait_basculer_la_decision(self) -> None:
        etudiante = StudentInput(
            "a",
            (
                SubjectGrade("FIQH", D("3"), D("5"), resit_value=D("12")),
                SubjectGrade("QURAN", D("5"), D("13")),
            ),
        )
        avant = compute_student(
            StudentInput(
                "a",
                (
                    SubjectGrade("FIQH", D("3"), D("5")),
                    SubjectGrade("QURAN", D("5"), D("13")),
                ),
            ),
            Rules(),
        )
        assert avant.decision is OverallDecision.RESIT

        apres = compute_student(etudiante, Rules())
        assert apres.average == D("12.6250000000")
        assert apres.decision is OverallDecision.PASSED
        fiqh = apres.subjects[0]
        assert fiqh.normal_value == D("5")
        assert fiqh.resit_value == D("12")
        assert fiqh.value == D("12")
        assert fiqh.decision is SubjectDecision.SATISFIED
        assert fiqh.improved_by_resit is True

    def test_les_matieres_non_repassees_gardent_leur_note(self) -> None:
        resultat = compute_student(
            StudentInput(
                "a",
                (
                    SubjectGrade("FIQH", D("3"), D("6"), resit_value=D("11")),
                    SubjectGrade("QURAN", D("5"), D("16")),
                ),
            ),
            Rules(),
        )
        quran = resultat.subjects[1]
        assert quran.value == D("16")
        assert quran.resit_value is None
        assert quran.improved_by_resit is False

    def test_un_rattrapage_rate_ne_fait_pas_perdre_la_note_normale(self) -> None:
        resultat = compute_student(
            StudentInput("a", (SubjectGrade("A", D("1"), D("9"), resit_value=D("3")),)),
            Rules(),
        )
        assert resultat.average == D("9")
        assert resultat.subjects[0].value == D("9")
