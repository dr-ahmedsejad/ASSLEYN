"""
Passerelle entre la base et le moteur de calcul.

Le moteur (`engine.py`) ne connait pas Django. Ce module fait le va-et-vient :
il lit les notes, appelle le moteur, et materialise les resultats. C'est aussi
lui qui preserve les surcharges de decision prononcees par le jury lors d'un
recalcul, et qui sait quelles etudiantes sont convoquees au rattrapage.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import QuerySet

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    ExamSession,
    Section,
    Semester,
)
from apps.grading.models import AbsencePolicy as DBAbsencePolicy
from apps.grading.models import Grade, GradeStatus, GradingRule
from apps.grading.models import RankingMode as DBRankingMode
from apps.grading.models import ResitPolicy as DBResitPolicy
from apps.results import engine
from apps.results.models import AnnualResult, SemesterResult, SubjectResult

logger = logging.getLogger("asleyn.audit")


class RuleNotConfigured(Exception):
    """Aucun reglement applicable : refuser de calculer plutot que d'inventer."""


class ThresholdOutOfRange(ValueError):
    """Barre de reussite hors des bornes du bareme."""


# --------------------------------------------------------------------------
# Reglement
# --------------------------------------------------------------------------


def resolve_rule(
    year: AcademicYear, section: Section, semester: Semester | None = None
) -> GradingRule:
    """
    Reglement applicable, du plus precis au plus general.

    Un seuil arrete en deliberation pour un قسم et un فصل prime sur la regle
    de la section, qui prime elle-meme sur celle de l'annee. C'est ce qui
    permet a la commission de fixer une barre propre a chaque classe sans
    toucher aux autres.
    """
    portees = []
    if semester is not None:
        portees.append({"section": section, "semester": semester})
        portees.append({"section": None, "semester": semester})
    portees.append({"section": section, "semester": None})
    portees.append({"section": None, "semester": None})

    for portee in portees:
        rule = (
            GradingRule.objects.filter(year=year, is_active=True, **portee)
            .order_by("-version")
            .first()
        )
        if rule is not None:
            return rule

    raise RuleNotConfigured(
        f"Aucune قاعدة تقويم active pour {year.label} / {section.name_ar}."
    )


def to_engine_rules(rule: GradingRule) -> engine.Rules:
    """Traduit le reglement stocke en base en reglement du moteur."""
    return engine.Rules(
        max_grade=rule.max_grade,
        pass_threshold=rule.pass_threshold,
        compensation_floor=rule.compensation_floor,
        ranking_mode=(
            engine.RankingMode.DENSE
            if rule.ranking_mode == DBRankingMode.DENSE
            else engine.RankingMode.STANDARD
        ),
        absence_policy=(
            engine.AbsencePolicy.COUNT_AS_ZERO
            if rule.absence_policy == DBAbsencePolicy.COUNT_AS_ZERO
            else engine.AbsencePolicy.EXCLUDE
        ),
        rounding_decimals=rule.rounding_decimals,
        resit_policy={
            DBResitPolicy.BEST: engine.ResitPolicy.BEST,
            DBResitPolicy.REPLACE: engine.ResitPolicy.REPLACE,
            DBResitPolicy.BEST_CAPPED: engine.ResitPolicy.BEST_CAPPED,
        }[rule.resit_policy],
    )


@transaction.atomic
def set_section_threshold(
    *,
    semester: Semester,
    section: Section,
    pass_threshold: Decimal,
    user,
    compensation_floor: Decimal | None = None,
    note: str = "",
) -> GradingRule:
    """
    Fixe en deliberation les seuils d'un قسم pour un فصل.

    `compensation_floor` a None laisse le plancher suivre la barre : il
    conserve sa valeur, sauf si celle-ci depasse desormais la barre de
    reussite — auquel cas il s'aligne dessus.

    Une nouvelle version du reglement est creee plutot que l'ancienne
    modifiee : les resultats deja calcules gardent la reference de la regle
    qui les a produits, et la commission dispose d'un historique de ses
    propres decisions.
    """
    base = resolve_rule(semester.year, section, semester)

    if pass_threshold > base.max_grade:
        raise ThresholdOutOfRange(
            f"La barre de reussite ne peut pas depasser {base.max_grade}."
        )

    # Le plancher de compensation est par definition une note eliminatoire :
    # il ne peut pas se retrouver au-dessus de la barre de reussite. Qu'il
    # soit choisi par la commission ou herite, on le borne — plutot que de
    # refuser une deliberation legitime ou de laisser un reglement incoherent.
    if compensation_floor is None:
        compensation_floor = base.compensation_floor
    if compensation_floor < 0:
        raise ThresholdOutOfRange("Le plancher de compensation ne peut pas etre negatif.")
    compensation_floor = min(compensation_floor, pass_threshold)

    derniere = (
        GradingRule.objects.filter(
            year=semester.year, section=section, semester=semester
        )
        .order_by("-version")
        .first()
    )

    rule = GradingRule.objects.create(
        year=semester.year,
        section=section,
        semester=semester,
        version=(derniere.version + 1) if derniere else 1,
        max_grade=base.max_grade,
        pass_threshold=pass_threshold,
        compensation_floor=compensation_floor,
        ranking_mode=base.ranking_mode,
        absence_policy=base.absence_policy,
        rounding_decimals=base.rounding_decimals,
        resit_policy=base.resit_policy,
        created_by=user,
        note=note,
    )
    logger.info(
        "Seuil de reussite fixe — %s / %s : %s (plancher %s, v%d) par %s — %s",
        section.name_ar,
        semester,
        pass_threshold,
        compensation_floor,
        rule.version,
        getattr(user, "username", "?"),
        note or "sans motif",
    )
    return rule


# --------------------------------------------------------------------------
# Lecture des notes
# --------------------------------------------------------------------------


def _curricula(section: Section, semester: Semester) -> list[Curriculum]:
    return list(
        Curriculum.objects.filter(
            section=section, semester=semester, is_active=True
        ).select_related("subject")
    )


def _enrollments(section: Section, semester: Semester) -> QuerySet[Enrollment]:
    return Enrollment.objects.filter(
        section=section, year=semester.year, is_active=True
    ).select_related("student")


def _notes_par_session(
    enrollments: QuerySet[Enrollment] | list[Enrollment],
    curricula: list[Curriculum],
    session: str,
) -> dict[tuple[int, int], Grade]:
    """Notes indexees par (inscription, matiere) pour une session donnee."""
    return {
        (g.enrollment_id, g.curriculum_id): g
        for g in Grade.objects.filter(
            enrollment__in=enrollments, curriculum__in=curricula, session=session
        )
    }


def _build_inputs(
    enrollments: list[Enrollment], curricula: list[Curriculum], session: str
) -> list[engine.StudentInput]:
    """
    Assemble les entrees du moteur.

    Pour la session normale, seules les notes de cette session comptent. Pour
    la session de rattrapage, on presente les deux notes au moteur : c'est lui
    qui applique la regle du reglement pour retenir la bonne.

    Une matiere du programme sans note enregistree est presentee comme une
    note absente : c'est le reglement, et non ce module, qui decide si cela
    vaut zero ou une exclusion.
    """
    normales = _notes_par_session(enrollments, curricula, ExamSession.NORMAL)
    rattrapages = (
        _notes_par_session(enrollments, curricula, ExamSession.RESIT)
        if session == ExamSession.RESIT
        else {}
    )

    inputs: list[engine.StudentInput] = []
    for enrollment in enrollments:
        subject_grades = []
        for curriculum in curricula:
            cle = (enrollment.id, curriculum.id)
            normale = normales.get(cle)
            rattrapage = rattrapages.get(cle)
            subject_grades.append(
                engine.SubjectGrade(
                    subject_code=str(curriculum.id),
                    coefficient=curriculum.coefficient,
                    value=normale.value if normale else None,
                    resit_value=rattrapage.value if rattrapage else None,
                    counts=not (normale and normale.status == GradeStatus.EXEMPT),
                )
            )
        inputs.append(
            engine.StudentInput(
                student_key=str(enrollment.id), grades=tuple(subject_grades)
            )
        )
    return inputs


# --------------------------------------------------------------------------
# Rattrapage
# --------------------------------------------------------------------------


def resit_candidates(semester: Semester, curriculum: Curriculum) -> set[int]:
    """
    Inscriptions convoquees au rattrapage dans une matiere.

    Regle de l'institut : on ne repasse que les matieres declarees
    غير مستوفي a l'issue de la session normale — et seulement si la decision
    globale retenue etait استدراك.
    """
    return set(
        SubjectResult.objects.filter(
            curriculum=curriculum,
            decision="NOT_SATISFIED",
            semester_result__semester=semester,
            semester_result__session=ExamSession.NORMAL,
            semester_result__decision_final="RESIT",
        ).values_list("semester_result__enrollment_id", flat=True)
    )


def retained_results(
    semester: Semester, enrollments: list[Enrollment] | QuerySet[Enrollment]
) -> dict[int, SemesterResult]:
    """
    Resultat retenu par etudiante pour un فصل : celui du rattrapage s'il
    existe, celui de la session normale sinon.
    """
    retenus: dict[int, SemesterResult] = {}
    for resultat in SemesterResult.objects.filter(
        semester=semester, enrollment__in=enrollments
    ).select_related("semester"):
        ancien = retenus.get(resultat.enrollment_id)
        if ancien is None or resultat.session == ExamSession.RESIT:
            retenus[resultat.enrollment_id] = resultat
    return retenus


# --------------------------------------------------------------------------
# Calcul et materialisation
# --------------------------------------------------------------------------

_SUBJECT_DECISION_MAP = {
    engine.SubjectDecision.SATISFIED: "SATISFIED",
    engine.SubjectDecision.NOT_SATISFIED: "NOT_SATISFIED",
    engine.SubjectDecision.NOT_APPLICABLE: "NOT_APPLICABLE",
}


@transaction.atomic
def recompute_semester(
    semester: Semester, section: Section, session: str | None = None
) -> int:
    """
    Recalcule un فصل pour une section et materialise les resultats.

    `session` vaut par defaut la session en cours du فصل. Chaque session a son
    propre resultat : celui de la session normale reste consultable apres le
    rattrapage, puisque c'est lui qui a fonde la convocation.

    Les surcharges de decision prononcees par le jury sont conservees : le
    recalcul met a jour `decision_computed`, jamais `decision_final` quand
    celle-ci a ete explicitement modifiee.

    Retourne le nombre d'etudiantes traitees.
    """
    session = session or semester.current_session

    curricula = _curricula(section, semester)
    if not curricula:
        logger.warning(
            "Recalcul ignore : aucun programme pour %s / %s",
            section.name_ar,
            semester,
        )
        return 0

    rule = resolve_rule(semester.year, section, semester)
    enrollments = list(_enrollments(section, semester))
    if not enrollments:
        return 0

    results = engine.compute_semester(
        _build_inputs(enrollments, curricula, session), to_engine_rules(rule)
    )
    cohort_size = len(results)
    curriculum_by_id = {str(c.id): c for c in curricula}
    enrollment_by_id = {str(e.id): e for e in enrollments}

    existants = {
        r.enrollment_id: r
        for r in SemesterResult.objects.filter(
            enrollment__in=enrollments, semester=semester, session=session
        )
    }

    traites: list[SemesterResult] = []
    for result in results:
        enrollment = enrollment_by_id[result.student_key]
        decision_calculee = result.decision.value
        ancien = existants.get(enrollment.id)

        # On ne conserve la decision finale que si le jury l'a explicitement
        # dissociee du calcul ; sinon elle suit le calcul.
        if ancien and ancien.decision_final != ancien.decision_computed:
            decision_finale = ancien.decision_final
            motif = ancien.override_reason
            auteur_id = ancien.overridden_by_id
        else:
            decision_finale = decision_calculee
            motif = ""
            auteur_id = None

        semester_result, _ = SemesterResult.objects.update_or_create(
            enrollment=enrollment,
            semester=semester,
            session=session,
            defaults={
                "average": result.average,
                "total_weighted": result.total_weighted,
                "total_coefficient": result.total_coefficient,
                "rank": result.rank,
                "cohort_size": cohort_size,
                "decision_computed": decision_calculee,
                "decision_final": decision_finale,
                "override_reason": motif,
                "overridden_by_id": auteur_id,
                "rule": rule,
            },
        )

        traites.append(semester_result)

        for outcome in result.subjects:
            curriculum = curriculum_by_id[outcome.subject_code]
            SubjectResult.objects.update_or_create(
                semester_result=semester_result,
                curriculum=curriculum,
                defaults={
                    "value": outcome.value,
                    "normal_value": outcome.normal_value,
                    "resit_value": outcome.resit_value,
                    "effective_value": outcome.effective_value,
                    "coefficient": outcome.coefficient,
                    "decision": _SUBJECT_DECISION_MAP[outcome.decision],
                },
            )

    # Resultats de matiere devenus etrangers au programme.
    #
    # Deux situations les produisent : une matiere retiree du programme, et une
    # etudiante qui change de قسم en cours d'annee — son releve porterait alors
    # les matieres des deux programmes. `update_or_create` ne pouvait pas les
    # voir : il ne visite que les matieres du programme courant.
    if traites:
        perimes = SubjectResult.objects.filter(semester_result__in=traites).exclude(
            curriculum__in=curricula
        )
        supprimes = perimes.delete()[0]
        if supprimes:
            logger.info(
                "Recalcul %s / %s : %d resultat(s) de matiere hors programme retire(s)",
                section.name_ar,
                semester,
                supprimes,
            )

    logger.info(
        "Recalcul %s / %s (%s) : %d etudiantes, seuil %s, regle v%d",
        section.name_ar,
        semester,
        session,
        cohort_size,
        rule.pass_threshold,
        rule.version,
    )
    return cohort_size


def recompute_semester_all_sections(
    semester: Semester, session: str | None = None
) -> dict[str, int]:
    """Recalcule toutes les sections ayant un programme sur ce فصل."""
    sections = Section.objects.filter(
        curricula__semester=semester, curricula__is_active=True
    ).distinct()
    return {s.name_ar: recompute_semester(semester, s, session) for s in sections}


@transaction.atomic
def recompute_annual(year: AcademicYear, section: Section) -> int:
    """
    Calcule les resultats annuels d'une section.

    La moyenne annuelle est la moyenne ponderee des فصول par leur `weight` —
    soit, avec les poids par defaut, la moyenne arithmetique des deux. Pour
    chaque فصل on prend le resultat **retenu** : celui du rattrapage quand il
    existe, celui de la session normale sinon.
    """
    rule = resolve_rule(year, section)
    semesters = list(Semester.objects.filter(year=year))
    if not semesters:
        return 0

    enrollments = list(
        Enrollment.objects.filter(section=section, year=year, is_active=True)
    )
    if not enrollments:
        return 0

    par_etudiante: dict[int, list[engine.SemesterAverage]] = {}
    for semester in semesters:
        for enrollment_id, resultat in retained_results(semester, enrollments).items():
            par_etudiante.setdefault(enrollment_id, []).append(
                engine.SemesterAverage(
                    semester_number=semester.number,
                    average=resultat.average,
                    weight=semester.weight,
                )
            )

    entrees = [
        engine.AnnualInput(
            student_key=str(e.id), semesters=tuple(par_etudiante.get(e.id, []))
        )
        for e in enrollments
    ]
    calcules = engine.compute_annual(
        entrees, to_engine_rules(rule), required_semesters=len(semesters)
    )

    enrollment_by_id = {str(e.id): e for e in enrollments}
    existants = {
        r.enrollment_id: r
        for r in AnnualResult.objects.filter(enrollment__in=enrollments, year=year)
    }

    for result in calcules:
        enrollment = enrollment_by_id[result.student_key]
        ancien = existants.get(enrollment.id)
        decision_calculee = result.decision.value
        if ancien and ancien.decision_final != ancien.decision_computed:
            decision_finale = ancien.decision_final
            motif = ancien.override_reason
            auteur_id = ancien.overridden_by_id
        else:
            decision_finale = decision_calculee
            motif = ""
            auteur_id = None

        AnnualResult.objects.update_or_create(
            enrollment=enrollment,
            year=year,
            defaults={
                "average": result.average,
                "rank": result.rank,
                "cohort_size": len(calcules),
                "semester_count": result.semester_count,
                "decision_computed": decision_calculee,
                "decision_final": decision_finale,
                "override_reason": motif,
                "overridden_by_id": auteur_id,
            },
        )

    logger.info(
        "Recalcul annuel %s / %s : %d etudiantes",
        section.name_ar,
        year.label,
        len(calcules),
    )
    return len(calcules)


def default_rule_for(year: AcademicYear) -> GradingRule:
    """
    Cree, si besoin, le reglement par defaut de l'annee.

    Les valeurs sont celles reconstituees du fichier 2025-2026 : /20, seuil 10,
    plancher de compensation 7, classement dense, absence comptee zero, et au
    rattrapage la meilleure des deux notes.
    """
    rule, cree = GradingRule.objects.get_or_create(
        year=year,
        section=None,
        semester=None,
        version=1,
        defaults={
            "max_grade": Decimal("20"),
            "pass_threshold": Decimal("10"),
            "compensation_floor": Decimal("7"),
            "ranking_mode": DBRankingMode.DENSE,
            "absence_policy": DBAbsencePolicy.COUNT_AS_ZERO,
            "resit_policy": DBResitPolicy.BEST,
            "rounding_decimals": 2,
        },
    )
    if cree:
        logger.info("Reglement par defaut cree pour %s", year.label)
    return rule
