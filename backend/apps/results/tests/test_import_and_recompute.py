"""
Test de bout en bout : import des donnees reelles, calcul en base, comparaison
au fichier d'origine.

Le test unitaire du moteur (`test_engine_golden.py`) prouve que l'algorithme
est juste. Celui-ci prouve que la chaine complete — modele de donnees, lecture
des notes, reglement stocke en base, materialisation des resultats — donne le
meme resultat que l'institut, sur ses vraies donnees.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.academics.models import AcademicYear, Curriculum, Enrollment, Section, Semester
from apps.accounts.models import Student
from apps.grading.models import Grade, GradeStatus
from apps.results.models import SemesterResult, SubjectResult
from apps.results.tests.test_engine_golden import KNOWN_RANK_ERRORS

FIXTURE = Path(__file__).parent / "fixtures" / "golden_fasl1_2025_2026.json"
TOLERANCE = Decimal("0.00000001")


@pytest.fixture(scope="module")
def golden() -> dict:
    with FIXTURE.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def imported(db) -> None:
    """Import complet des 98 lignes, le conflit de matricule etant arbitre."""
    call_command("seed_2025_2026", verbosity=0)


@pytest.mark.django_db
def test_structure_importee(imported: None, golden: dict) -> None:
    year = AcademicYear.objects.get(label="2025-2026")
    assert year.is_active is True
    assert Semester.objects.filter(year=year).count() == 2

    assert Section.objects.count() == 5
    # 4 + 4 + 5 + 2 + 4 matieres reparties sur les cinq sections
    assert Curriculum.objects.count() == sum(
        len(s["coefficients"]) for s in golden["sections"]
    )
    assert Student.objects.count() == 98
    assert Enrollment.objects.count() == 98


@pytest.mark.django_db
def test_coefficients_conformes_au_fichier(imported: None, golden: dict) -> None:
    for bloc in golden["sections"]:
        section = Section.objects.get(code=bloc["code"])
        for code, coef in bloc["coefficients"].items():
            curriculum = Curriculum.objects.get(
                section=section, subject__code=code, semester__number=1
            )
            assert curriculum.coefficient == Decimal(str(coef))


@pytest.mark.django_db
def test_absences_distinguees_des_zeros(imported: None, golden: dict) -> None:
    """
    Ce que le fichier Excel ne savait pas exprimer : une cellule vide devient
    un statut « غائبة », pas une note de zero.
    """
    attendu = sum(
        1
        for bloc in golden["sections"]
        for etudiante in bloc["students"]
        for note in etudiante["grades"].values()
        if note is None
    )
    assert Grade.objects.filter(status=GradeStatus.ABSENT).count() == attendu
    assert Grade.objects.filter(status=GradeStatus.ABSENT, value__isnull=False).count() == 0


@pytest.mark.django_db
def test_resultats_en_base_identiques_au_fichier(imported: None, golden: dict) -> None:
    """Moyennes, decisions et rangs, compares ligne a ligne au fichier source."""
    ecarts: list[str] = []

    for bloc in golden["sections"]:
        section = Section.objects.get(code=bloc["code"])
        resultats = {
            r.enrollment.student.full_name_ar: r
            for r in SemesterResult.objects.filter(
                enrollment__section=section, semester__number=1
            ).select_related("enrollment__student")
        }
        assert len(resultats) == len(bloc["students"]), (
            f"{bloc['name_ar']} : {len(resultats)} resultats pour "
            f"{len(bloc['students'])} etudiantes"
        )

        for etudiante in bloc["students"]:
            nom = etudiante["full_name_ar"]
            resultat = resultats[nom]

            attendu = Decimal(str(etudiante["excel_average"]))
            if abs(resultat.average - attendu) > TOLERANCE:
                ecarts.append(
                    f"moyenne {bloc['name_ar']}/{nom} : "
                    f"fichier={attendu} base={resultat.average}"
                )

            if resultat.decision_computed != etudiante["excel_decision"]:
                ecarts.append(
                    f"decision {bloc['name_ar']}/{nom} : "
                    f"fichier={etudiante['excel_decision']} "
                    f"base={resultat.decision_computed}"
                )

            cle = (bloc["code"], etudiante["matricule"])
            rang_attendu = (
                KNOWN_RANK_ERRORS[cle]["correct"]
                if cle in KNOWN_RANK_ERRORS
                else etudiante["excel_rank"]
            )
            if resultat.rank != rang_attendu:
                ecarts.append(
                    f"rang {bloc['name_ar']}/{nom} : "
                    f"attendu={rang_attendu} base={resultat.rank}"
                )

    assert not ecarts, "\n".join(ecarts)


@pytest.mark.django_db
def test_detail_par_matiere_materialise(imported: None, golden: dict) -> None:
    """Chaque resultat porte une ligne par matiere, avec la bonne decision."""
    for bloc in golden["sections"]:
        section = Section.objects.get(code=bloc["code"])
        for resultat in SemesterResult.objects.filter(
            enrollment__section=section, semester__number=1
        ).select_related("enrollment__student"):
            nom = resultat.enrollment.student.full_name_ar
            attendu = next(
                s for s in bloc["students"] if s["full_name_ar"] == nom
            )["excel_subject_decisions"]

            lignes = {
                sr.curriculum.subject.code: sr
                for sr in SubjectResult.objects.filter(
                    semester_result=resultat
                ).select_related("curriculum__subject")
            }
            assert set(lignes) == set(attendu), f"{bloc['name_ar']}/{nom}"
            for code, decision in attendu.items():
                assert lignes[code].decision == decision, (
                    f"{bloc['name_ar']}/{nom}/{code} : "
                    f"fichier={decision} base={lignes[code].decision}"
                )


@pytest.mark.django_db
def test_import_idempotent(imported: None) -> None:
    """Relancer l'import ne cree ni doublon ni resultat supplementaire."""
    avant = (
        Student.objects.count(),
        Enrollment.objects.count(),
        Grade.objects.count(),
        SemesterResult.objects.count(),
    )
    call_command("seed_2025_2026", "--provisional-matricules", verbosity=0)
    apres = (
        Student.objects.count(),
        Enrollment.objects.count(),
        Grade.objects.count(),
        SemesterResult.objects.count(),
    )
    assert avant == apres


@pytest.mark.django_db
def test_matricule_unique_en_base(imported: None) -> None:
    """
    Le conflit du fichier source ne peut pas se reproduire : les deux
    etudiantes portent desormais deux matricules distincts, conformes a
    l'arbitrage de la direction.
    """
    matricules = list(Student.objects.values_list("matricule", flat=True))
    assert len(matricules) == len(set(matricules))
    # L'arbitrage rend le numero provisoire inutile.
    assert not Student.objects.filter(matricule__startswith="99").exists()

    assert Student.objects.get(matricule="24097").full_name_ar == "أمبيغية أمينو"
    tbrak = Student.objects.get(matricule="24098")
    assert tbrak.full_name_ar == "تبراك اسليمان"
    assert tbrak.enrollments.get().section.code == "MUTAMAYYIZAT"


@pytest.mark.django_db
def test_le_recalcul_preserve_une_decision_de_jury(imported: None) -> None:
    """
    Le jury peut surcharger une decision ; un recalcul ulterieur met a jour le
    calcul sans effacer la decision retenue.
    """
    from apps.results.services import recompute_semester

    resultat = SemesterResult.objects.filter(decision_computed="RESIT").first()
    assert resultat is not None
    resultat.decision_final = "PASSED"
    resultat.override_reason = "قرار مجلس القسم"
    resultat.save()

    recompute_semester(resultat.semester, resultat.enrollment.section)

    resultat.refresh_from_db()
    assert resultat.decision_computed == "RESIT"
    assert resultat.decision_final == "PASSED"
    assert resultat.override_reason == "قرار مجلس القسم"
    assert resultat.is_overridden is True
