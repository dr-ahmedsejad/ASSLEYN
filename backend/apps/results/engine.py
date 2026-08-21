"""
Moteur de calcul des resultats.

Module volontairement **pur** : aucun import Django, aucun acces base, aucune
entree/sortie. Il prend des donnees, il rend des donnees. Cela le rend
testable exhaustivement, rejouable sur des donnees historiques et reutilisable
pour de la simulation.

Les regles implementees ici ont ete reconstituees a partir des formules du
fichier « Résultat Trimestre 1 - A2 - 2025-2026.xlsx », puis validees : le
moteur reproduit a l'identique les 98 moyennes et les 98 decisions du fichier
d'origine (voir apps/results/tests/test_engine_golden.py).

    moyenne  = Σ (note × coefficient) / Σ (coefficients)

    matiere  = مستوفي      si note ≥ عتبة النجاح
                            ou (moyenne ≥ عتبة النجاح et note ≥ حد التعويض)
               غير مستوفي   sinon

    globale  = ناجحة       si moyenne ≥ عتبة النجاح
                            et toutes les notes ≥ حد التعويض
               استدراك      sinon

Precision : toutes les comparaisons portent sur la moyenne **non arrondie**,
comme dans le fichier d'origine. L'arrondi n'intervient qu'a l'affichage.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

# Precision interne de la moyenne. Suffisamment fine pour que deux etudiantes
# reellement a egalite le restent, et pour que la division ne cree pas
# d'ecarts artificiels.
_INTERNAL_PRECISION = Decimal("0.0000000001")

ZERO = Decimal("0")


class RankingMode(str, Enum):
    """1, 2, 3, 3, 4 (DENSE) ou 1, 2, 3, 3, 5 (STANDARD)."""

    DENSE = "DENSE"
    STANDARD = "STANDARD"


class AbsencePolicy(str, Enum):
    COUNT_AS_ZERO = "ZERO"
    EXCLUDE = "EXCLUDE"


class ResitPolicy(str, Enum):
    """
    Comment la note de rattrapage se combine a celle de la session normale.

    L'institut retient BEST : une etudiante ne peut jamais perdre de points en
    repassant une matiere. Les deux autres regles sont implementees mais
    inactives — changer de politique se fait dans le reglement, pas ici.
    """

    BEST = "BEST"
    REPLACE = "REPLACE"
    BEST_CAPPED = "BEST_CAPPED"


class SubjectDecision(str, Enum):
    SATISFIED = "SATISFIED"          # مستوفي
    NOT_SATISFIED = "NOT_SATISFIED"  # غير مستوفي
    NOT_APPLICABLE = "NOT_APPLICABLE"  # matiere dont l'etudiante est dispensee


class OverallDecision(str, Enum):
    PASSED = "PASSED"  # ناجحة
    RESIT = "RESIT"    # استدراك


@dataclass(frozen=True)
class Rules:
    """Reglement applique. Reflete le modele `grading.GradingRule`."""

    max_grade: Decimal = Decimal("20")
    pass_threshold: Decimal = Decimal("10")
    compensation_floor: Decimal = Decimal("7")
    ranking_mode: RankingMode = RankingMode.DENSE
    absence_policy: AbsencePolicy = AbsencePolicy.COUNT_AS_ZERO
    rounding_decimals: int = 2
    resit_policy: ResitPolicy = ResitPolicy.BEST

    def __post_init__(self) -> None:
        if self.compensation_floor > self.pass_threshold:
            raise ValueError(
                "Le plancher de compensation ne peut pas depasser le seuil de reussite."
            )
        if self.pass_threshold > self.max_grade:
            raise ValueError(
                "Le seuil de reussite ne peut pas depasser la note maximale."
            )
        if self.rounding_decimals < 0:
            raise ValueError("Le nombre de decimales doit etre positif ou nul.")


@dataclass(frozen=True)
class SubjectGrade:
    """
    Note d'une etudiante dans une matiere.

    `value` a None signifie « pas de note mesuree » : absence, absence
    justifiee, ou saisie non encore effectuee. La facon de la traiter est
    decidee par le reglement, pas par l'appelant.

    `counts` a False retire completement la matiere du calcul (dispense) :
    son coefficient disparait aussi du denominateur.
    """

    subject_code: str
    coefficient: Decimal
    value: Decimal | None = None
    counts: bool = True
    #: Note obtenue a la session de rattrapage, si l'etudiante l'a passee.
    resit_value: Decimal | None = None

    def __post_init__(self) -> None:
        if self.coefficient <= ZERO:
            raise ValueError(
                f"Coefficient invalide pour {self.subject_code} : {self.coefficient}"
            )
        for etiquette, note in (
            ("Note", self.value),
            ("Note de rattrapage", self.resit_value),
        ):
            if note is not None and note < ZERO:
                raise ValueError(
                    f"{etiquette} negative pour {self.subject_code} : {note}"
                )


@dataclass(frozen=True)
class StudentInput:
    """Ensemble des notes d'une etudiante pour un فصل."""

    student_key: str
    grades: tuple[SubjectGrade, ...]


@dataclass(frozen=True)
class SubjectOutcome:
    subject_code: str
    coefficient: Decimal
    value: Decimal | None  # note retenue apres application de la regle de rattrapage
    normal_value: Decimal | None
    resit_value: Decimal | None
    effective_value: Decimal | None  # valeur reellement injectee dans la moyenne
    decision: SubjectDecision

    @property
    def improved_by_resit(self) -> bool:
        return self.resit_value is not None and self.value == self.resit_value


@dataclass(frozen=True)
class StudentResult:
    student_key: str
    average: Decimal
    total_weighted: Decimal
    total_coefficient: Decimal
    decision: OverallDecision
    subjects: tuple[SubjectOutcome, ...]
    rank: int = 0
    has_no_counted_subject: bool = False

    @property
    def average_display(self) -> Decimal:
        """Moyenne telle qu'elle apparait sur le bulletin."""
        return self.average


# --------------------------------------------------------------------------
# Calcul d'un فصل
# --------------------------------------------------------------------------


def retained_value(grade: SubjectGrade, rules: Rules) -> Decimal | None:
    """
    Note retenue pour une matiere, une fois la session de rattrapage prise en
    compte.

    Sans note de rattrapage, c'est la note de la session normale. Sinon la
    regle du reglement s'applique — a l'institut, la meilleure des deux, pour
    qu'une etudiante ne puisse jamais perdre de points en repassant.
    """
    normale, rattrapage = grade.value, grade.resit_value
    if rattrapage is None:
        return normale

    if rules.resit_policy is ResitPolicy.REPLACE:
        retenue = rattrapage
    else:
        retenue = rattrapage if normale is None else max(normale, rattrapage)
        if rules.resit_policy is ResitPolicy.BEST_CAPPED:
            # La note issue du rattrapage ne depasse pas la barre de reussite,
            # mais une meilleure note de session normale reste intacte.
            plafonnee = min(retenue, rules.pass_threshold)
            retenue = plafonnee if normale is None else max(normale, plafonnee)
    return retenue


def _effective_value(grade: SubjectGrade, rules: Rules) -> Decimal | None:
    """Valeur reellement prise en compte, ou None si la matiere est exclue."""
    if not grade.counts:
        return None
    retenue = retained_value(grade, rules)
    if retenue is not None:
        return retenue
    if rules.absence_policy is AbsencePolicy.COUNT_AS_ZERO:
        return ZERO
    return None  # EXCLUDE : la matiere sort du calcul


def _weighted_average(
    grades: tuple[SubjectGrade, ...], rules: Rules
) -> tuple[Decimal, Decimal, Decimal]:
    """Retourne (moyenne, total pondere, total des coefficients)."""
    total_weighted = ZERO
    total_coefficient = ZERO
    for grade in grades:
        effective = _effective_value(grade, rules)
        if effective is None:
            continue
        total_weighted += effective * grade.coefficient
        total_coefficient += grade.coefficient

    if total_coefficient == ZERO:
        return ZERO, ZERO, ZERO

    average = (total_weighted / total_coefficient).quantize(_INTERNAL_PRECISION)
    return average, total_weighted, total_coefficient


def _subject_decision(
    effective: Decimal | None, average: Decimal, rules: Rules
) -> SubjectDecision:
    """
    Decision par matiere, avec compensation.

    Une note comprise entre le plancher de compensation et le seuil de
    reussite est rattrapee si la moyenne generale atteint le seuil. C'est la
    raison pour laquelle cette decision ne peut etre calculee qu'apres la
    moyenne.
    """
    if effective is None:
        return SubjectDecision.NOT_APPLICABLE
    if effective >= rules.pass_threshold:
        return SubjectDecision.SATISFIED
    if average >= rules.pass_threshold and effective >= rules.compensation_floor:
        return SubjectDecision.SATISFIED
    return SubjectDecision.NOT_SATISFIED


def compute_student(student: StudentInput, rules: Rules) -> StudentResult:
    """Calcule moyenne, decisions par matiere et decision globale (sans rang)."""
    average, total_weighted, total_coefficient = _weighted_average(
        student.grades, rules
    )

    outcomes: list[SubjectOutcome] = []
    all_above_floor = True
    for grade in student.grades:
        effective = _effective_value(grade, rules)
        outcomes.append(
            SubjectOutcome(
                subject_code=grade.subject_code,
                coefficient=grade.coefficient,
                value=retained_value(grade, rules),
                normal_value=grade.value,
                resit_value=grade.resit_value,
                effective_value=effective,
                decision=_subject_decision(effective, average, rules),
            )
        )
        if effective is not None and effective < rules.compensation_floor:
            all_above_floor = False

    passed = average >= rules.pass_threshold and all_above_floor
    return StudentResult(
        student_key=student.student_key,
        average=average,
        total_weighted=total_weighted,
        total_coefficient=total_coefficient,
        decision=OverallDecision.PASSED if passed else OverallDecision.RESIT,
        subjects=tuple(outcomes),
        has_no_counted_subject=total_coefficient == ZERO,
    )


def assign_ranks(
    results: list[StudentResult], mode: RankingMode = RankingMode.DENSE
) -> list[StudentResult]:
    """
    Classe par moyenne decroissante et attribue les rangs.

    En mode DENSE, les ex aequo partagent le rang et le suivant reprend a
    rang + 1 (1, 2, 3, 3, 4). C'est la convention de l'institut.
    """
    ordered = sorted(results, key=lambda r: -r.average)
    ranked: list[StudentResult] = []
    previous_average: Decimal | None = None
    current_rank = 0

    for position, result in enumerate(ordered, start=1):
        if previous_average is None or result.average != previous_average:
            current_rank = current_rank + 1 if mode is RankingMode.DENSE else position
        ranked.append(replace(result, rank=current_rank))
        previous_average = result.average

    return ranked


def compute_semester(
    students: list[StudentInput], rules: Rules | None = None
) -> list[StudentResult]:
    """
    Point d'entree principal : calcule un فصل complet pour une section.

    Retourne les resultats classes, du premier rang au dernier.
    """
    rules = rules or Rules()
    computed = [compute_student(student, rules) for student in students]
    return assign_ranks(computed, rules.ranking_mode)


# --------------------------------------------------------------------------
# Calcul annuel
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SemesterAverage:
    """Moyenne d'un فصل et son poids dans la moyenne annuelle."""

    semester_number: int
    average: Decimal
    weight: Decimal = Decimal("1")


@dataclass(frozen=True)
class AnnualInput:
    student_key: str
    semesters: tuple[SemesterAverage, ...]


@dataclass(frozen=True)
class AnnualResult:
    student_key: str
    average: Decimal
    decision: OverallDecision
    rank: int = 0
    semester_count: int = 0


def compute_annual(
    students: list[AnnualInput],
    rules: Rules | None = None,
    required_semesters: int = 2,
) -> list[AnnualResult]:
    """
    Moyenne annuelle = moyenne ponderee des فصول.

    Avec les deux فصول a poids egal — la regle retenue par l'institut — cela
    revient a (moyenne_fasl_1 + moyenne_fasl_2) / 2. Les poids restent
    parametrables : passer un jour a une ponderation inegale ne demande aucune
    modification de ce code.

    Une etudiante a qui il manque un فصل est calculee sur ce qu'elle a, mais
    `semester_count` permet a l'appelant de signaler le dossier incomplet.
    """
    rules = rules or Rules()
    computed: list[AnnualResult] = []

    for student in students:
        total_weight = sum((s.weight for s in student.semesters), ZERO)
        if total_weight == ZERO:
            average = ZERO
        else:
            weighted = sum(
                (s.average * s.weight for s in student.semesters), ZERO
            )
            average = (weighted / total_weight).quantize(_INTERNAL_PRECISION)

        complete = len(student.semesters) >= required_semesters
        passed = complete and average >= rules.pass_threshold
        computed.append(
            AnnualResult(
                student_key=student.student_key,
                average=average,
                decision=OverallDecision.PASSED if passed else OverallDecision.RESIT,
                semester_count=len(student.semesters),
            )
        )

    ordered = sorted(computed, key=lambda r: -r.average)
    ranked: list[AnnualResult] = []
    previous: Decimal | None = None
    rank = 0
    for position, result in enumerate(ordered, start=1):
        if previous is None or result.average != previous:
            rank = rank + 1 if rules.ranking_mode is RankingMode.DENSE else position
        ranked.append(replace(result, rank=rank))
        previous = result.average
    return ranked


# --------------------------------------------------------------------------
# Utilitaire d'affichage
# --------------------------------------------------------------------------


def round_for_display(value: Decimal, decimals: int = 2) -> Decimal:
    """Arrondi commercial, utilise uniquement pour l'affichage et les bulletins."""
    quantum = Decimal(1).scaleb(-decimals)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)
