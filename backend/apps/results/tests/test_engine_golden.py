"""
Test de reference du moteur de calcul.

Le jeu de donnees est le fichier reel de l'institut :
« Résultat Trimestre 1 - A2 - 2025-2026.xlsx », 5 sections, 98 lignes.

Le contrat verifie ici est simple et non negociable : pour ces donnees, le
moteur doit produire **exactement** les moyennes et les decisions que
l'institut a produites. Si un jour ce test echoue, c'est que le reglement a
change — auquel cas la regle doit etre versionnee, pas le test assoupli.

Les seules divergences admises sont quatre rangs saisis a la main dans le
fichier source, dont l'erreur est demontree ci-dessous.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.results.engine import (
    OverallDecision,
    Rules,
    StudentInput,
    SubjectDecision,
    SubjectGrade,
    compute_semester,
)

FIXTURE = Path(__file__).parent / "fixtures" / "golden_fasl1_2025_2026.json"

# Quatre etudiantes de la section الحفيدات portent le rang 18 dans le fichier
# alors qu'elles sont a egalite parfaite (moyenne 0) avec une cinquieme qui,
# elle, porte le rang 19. Les cinq doivent partager le meme rang : 19.
# C'est une erreur de saisie manuelle, pas un desaccord de regle.
KNOWN_RANK_ERRORS = {
    ("HAFIDAT", "24065"): {"fichier": 18, "correct": 19},
    ("HAFIDAT", "24071"): {"fichier": 18, "correct": 19},
    ("HAFIDAT", "24073"): {"fichier": 18, "correct": 19},
    ("HAFIDAT", "24075"): {"fichier": 18, "correct": 19},
}

TOLERANCE = Decimal("0.00000001")


def load_golden() -> list[dict]:
    with FIXTURE.open(encoding="utf-8") as handle:
        return json.load(handle)["sections"]


def build_inputs(section: dict) -> list[StudentInput]:
    """Traduit une section du fichier en entrees du moteur."""
    coefficients = section["coefficients"]
    inputs = []
    for student in section["students"]:
        grades = tuple(
            SubjectGrade(
                subject_code=code,
                coefficient=Decimal(str(coefficients[code])),
                value=None if value is None else Decimal(str(value)),
            )
            for code, value in student["grades"].items()
        )
        # La cle est le matricule, sauf pour les deux lignes du fichier qui
        # partagent le matricule 24097 : on desambiguise par le numero de ligne.
        inputs.append(
            StudentInput(
                student_key=f"{section['code']}:{student['matricule']}:{student['row']}",
                grades=grades,
            )
        )
    return inputs


def results_by_row(section: dict) -> dict[int, object]:
    computed = compute_semester(build_inputs(section), Rules())
    return {int(r.student_key.rsplit(":", 1)[1]): r for r in computed}


SECTIONS = load_golden()
SECTION_IDS = [s["code"] for s in SECTIONS]


@pytest.mark.parametrize("section", SECTIONS, ids=SECTION_IDS)
def test_moyennes_identiques_au_fichier_source(section: dict) -> None:
    """La moyenne calculee doit egaler celle du fichier, a 1e-8 pres."""
    computed = results_by_row(section)
    for student in section["students"]:
        result = computed[student["row"]]
        attendu = Decimal(str(student["excel_average"]))
        ecart = abs(result.average - attendu)
        assert ecart <= TOLERANCE, (
            f"{section['name_ar']} ligne {student['row']} "
            f"({student['full_name_ar']}) : fichier={attendu} moteur={result.average}"
        )


@pytest.mark.parametrize("section", SECTIONS, ids=SECTION_IDS)
def test_decisions_globales_identiques(section: dict) -> None:
    """ناجحة / استدراك doivent correspondre ligne a ligne."""
    computed = results_by_row(section)
    for student in section["students"]:
        result = computed[student["row"]]
        attendu = OverallDecision(student["excel_decision"])
        assert result.decision is attendu, (
            f"{section['name_ar']} ligne {student['row']} "
            f"({student['full_name_ar']}) : fichier={attendu} moteur={result.decision}"
        )


@pytest.mark.parametrize("section", SECTIONS, ids=SECTION_IDS)
def test_decisions_par_matiere_identiques(section: dict) -> None:
    """مستوفي / غير مستوفي doivent correspondre pour chaque matiere."""
    computed = results_by_row(section)
    for student in section["students"]:
        result = computed[student["row"]]
        obtenues = {s.subject_code: s.decision for s in result.subjects}
        for code, attendu_str in student["excel_subject_decisions"].items():
            attendu = SubjectDecision(attendu_str)
            assert obtenues[code] is attendu, (
                f"{section['name_ar']} ligne {student['row']} "
                f"({student['full_name_ar']}) matiere {code} : "
                f"fichier={attendu} moteur={obtenues[code]}"
            )


@pytest.mark.parametrize("section", SECTIONS, ids=SECTION_IDS)
def test_rangs_identiques_hors_erreurs_connues(section: dict) -> None:
    """
    Le classement doit reproduire le fichier, sauf les quatre rangs
    manifestement mal saisis, pour lesquels on verifie que le moteur produit
    bien la valeur corrigee.
    """
    computed = results_by_row(section)
    for student in section["students"]:
        result = computed[student["row"]]
        cle = (section["code"], student["matricule"])
        if cle in KNOWN_RANK_ERRORS:
            assert result.rank == KNOWN_RANK_ERRORS[cle]["correct"], (
                f"{section['name_ar']} {student['matricule']} : le moteur doit "
                f"corriger le rang {KNOWN_RANK_ERRORS[cle]['fichier']} du fichier "
                f"en {KNOWN_RANK_ERRORS[cle]['correct']}"
            )
            continue
        assert result.rank == student["excel_rank"], (
            f"{section['name_ar']} ligne {student['row']} "
            f"({student['full_name_ar']}) : fichier={student['excel_rank']} "
            f"moteur={result.rank}"
        )


def test_le_jeu_de_reference_est_complet() -> None:
    """Garde-fou : le jeu ne doit pas retrecir silencieusement."""
    total = sum(len(s["students"]) for s in SECTIONS)
    assert len(SECTIONS) == 5
    assert total == 98
