"""
Changement de قسم en cours d'annee.

Une etudiante qui change de section garde son inscription — c'est la meme
ligne, avec une autre section. Son releve, lui, doit changer entierement de
programme : les matieres de l'ancien قسم n'ont plus a y figurer.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.academics.models import Curriculum, Section, Semester
from apps.grading.models import Grade, GradeStatus
from apps.results.models import SemesterResult, SubjectResult
from apps.results.services import recompute_semester


@pytest.mark.django_db
def test_le_releve_ne_garde_pas_les_matieres_de_l_ancien_qism(
    rule,
    enrollment,
    fasl1: Semester,
    section_a: Section,
    section_b: Section,
    curriculum_a_quran: Curriculum,
    curriculum_a_fiqh: Curriculum,
    curriculum_b_quran: Curriculum,
) -> None:
    """
    Le calcul ne visite que les matieres du programme courant : sans nettoyage,
    les resultats de l'ancien programme resteraient accroches au releve, qui
    afficherait les matieres des deux قسمين.
    """
    for curriculum in (curriculum_a_quran, curriculum_a_fiqh):
        Grade.objects.create(
            enrollment=enrollment,
            curriculum=curriculum,
            value=Decimal("15.00"),
            status=GradeStatus.ENTERED,
        )
    recompute_semester(fasl1, section_a)

    resultat = SemesterResult.objects.get(enrollment=enrollment, semester=fasl1)
    assert SubjectResult.objects.filter(semester_result=resultat).count() == 2

    # L'etudiante change de قسم.
    enrollment.section = section_b
    enrollment.save(update_fields=["section"])
    recompute_semester(fasl1, section_b)

    resultat.refresh_from_db()
    matieres = SubjectResult.objects.filter(semester_result=resultat)
    assert [m.curriculum_id for m in matieres] == [curriculum_b_quran.id]


@pytest.mark.django_db
def test_une_matiere_retiree_du_programme_quitte_le_releve(
    rule,
    enrollment,
    fasl1: Semester,
    section_a: Section,
    curriculum_a_quran: Curriculum,
    curriculum_a_fiqh: Curriculum,
) -> None:
    """Meme mecanique, cause differente : le programme lui-meme a change."""
    for curriculum in (curriculum_a_quran, curriculum_a_fiqh):
        Grade.objects.create(
            enrollment=enrollment,
            curriculum=curriculum,
            value=Decimal("12.00"),
            status=GradeStatus.ENTERED,
        )
    recompute_semester(fasl1, section_a)

    # Une matiere retiree du programme est desactivee, jamais supprimee :
    # elle porte deja des notes.
    curriculum_a_fiqh.is_active = False
    curriculum_a_fiqh.save(update_fields=["is_active"])
    recompute_semester(fasl1, section_a)

    resultat = SemesterResult.objects.get(enrollment=enrollment, semester=fasl1)
    matieres = SubjectResult.objects.filter(semester_result=resultat)
    assert [m.curriculum_id for m in matieres] == [curriculum_a_quran.id]
    # La moyenne ne porte plus que sur la matiere restante.
    assert resultat.total_coefficient == curriculum_a_quran.coefficient
