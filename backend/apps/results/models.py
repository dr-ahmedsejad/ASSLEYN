"""
Resultats calcules.

Ces tables sont **derivees** : aucun utilisateur n'y ecrit directement. Elles
sont materialisees plutot que recalculees a la volee pour deux raisons : un
bulletin deja emis doit rester identique s'il est reimprime, et le classement
doit etre interrogeable en SQL.

Le jury garde le dernier mot : `decision_final` peut differer de
`decision_computed`, mais seulement avec un motif et un auteur.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    ExamSession,
    Semester,
)
from apps.grading.models import GradingRule


class OverallDecision(models.TextChoices):
    PASSED = "PASSED", _("ناجحة")
    RESIT = "RESIT", _("استدراك")


class SubjectDecision(models.TextChoices):
    SATISFIED = "SATISFIED", _("مستوفي")
    NOT_SATISFIED = "NOT_SATISFIED", _("غير مستوفي")
    NOT_APPLICABLE = "NOT_APPLICABLE", _("لا ينطبق")


class SemesterResult(models.Model):
    """Resultat d'une etudiante pour un فصل."""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="semester_results",
        verbose_name=_("التسجيل"),
    )
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name=_("الفصل"),
    )
    # Un resultat par session : celui de la session normale reste consultable
    # apres le rattrapage, c'est lui qui a fonde la convocation.
    session = models.CharField(
        _("الدورة"),
        max_length=10,
        choices=ExamSession.choices,
        default=ExamSession.NORMAL,
    )

    average = models.DecimalField(_("المعدل"), max_digits=12, decimal_places=10)
    total_weighted = models.DecimalField(max_digits=12, decimal_places=4)
    total_coefficient = models.DecimalField(max_digits=8, decimal_places=2)
    rank = models.PositiveSmallIntegerField(_("الرتبة"))
    cohort_size = models.PositiveSmallIntegerField(_("عدد الطالبات"))

    decision_computed = models.CharField(
        _("القرار المحسوب"), max_length=10, choices=OverallDecision.choices
    )
    decision_final = models.CharField(
        _("قرار اللجنة"), max_length=10, choices=OverallDecision.choices
    )
    override_reason = models.CharField(_("سبب التعديل"), max_length=255, blank=True)
    overridden_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="decision_overrides",
        verbose_name=_("عدّلها"),
    )

    # Reglement effectivement applique : rend le resultat reproductible.
    rule = models.ForeignKey(
        GradingRule,
        on_delete=models.PROTECT,
        related_name="semester_results",
        verbose_name=_("قاعدة التقويم"),
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("نتيجة الفصل")
        verbose_name_plural = _("نتائج الفصول")
        ordering = ["semester", "session", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "semester", "session"],
                name="un_resultat_par_etudiante_fasl_et_dorra",
            )
        ]
        indexes = [models.Index(fields=["semester", "session", "rank"])]

    def __str__(self) -> str:
        return (
            f"{self.enrollment.student.matricule} — {self.semester} "
            f"({self.get_session_display()}) — {self.average}"
        )

    @property
    def is_overridden(self) -> bool:
        return self.decision_final != self.decision_computed

    def clean(self) -> None:
        if self.is_overridden and not self.override_reason:
            raise ValidationError(
                {"override_reason": _("تعديل قرار اللجنة يستوجب ذكر السبب.")}
            )


class SubjectResult(models.Model):
    """Detail par matiere d'un resultat de فصل."""

    semester_result = models.ForeignKey(
        SemesterResult,
        on_delete=models.CASCADE,
        related_name="subject_results",
        verbose_name=_("نتيجة الفصل"),
    )
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="subject_results",
        verbose_name=_("مادة الفصل"),
    )
    value = models.DecimalField(
        _("النقطة المعتمدة"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    normal_value = models.DecimalField(
        _("نقطة الدورة العادية"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    resit_value = models.DecimalField(
        _("نقطة الدورة الاستدراكية"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    effective_value = models.DecimalField(
        _("النقطة المحتسبة"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    coefficient = models.DecimalField(_("الضارب"), max_digits=4, decimal_places=2)
    decision = models.CharField(
        _("قرار اللجنة"), max_length=15, choices=SubjectDecision.choices
    )

    class Meta:
        verbose_name = _("نتيجة مادة")
        verbose_name_plural = _("نتائج المواد")
        ordering = ["curriculum__display_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["semester_result", "curriculum"],
                name="une_ligne_par_matiere_et_resultat",
            )
        ]

    def __str__(self) -> str:
        return f"{self.curriculum.subject.name_ar} = {self.value}"


class AnnualResult(models.Model):
    """Resultat annuel : moyenne des deux فصول."""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="annual_results",
        verbose_name=_("التسجيل"),
    )
    year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="annual_results",
        verbose_name=_("السنة الدراسية"),
    )
    average = models.DecimalField(_("المعدل السنوي"), max_digits=12, decimal_places=10)
    rank = models.PositiveSmallIntegerField(_("الرتبة السنوية"))
    cohort_size = models.PositiveSmallIntegerField(_("عدد الطالبات"))
    semester_count = models.PositiveSmallIntegerField(_("عدد الفصول المحتسبة"))

    decision_computed = models.CharField(max_length=10, choices=OverallDecision.choices)
    decision_final = models.CharField(
        _("القرار النهائي"), max_length=10, choices=OverallDecision.choices
    )
    override_reason = models.CharField(_("سبب التعديل"), max_length=255, blank=True)
    overridden_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="annual_overrides",
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("النتيجة السنوية")
        verbose_name_plural = _("النتائج السنوية")
        ordering = ["year", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "year"], name="un_resultat_annuel_par_etudiante"
            )
        ]

    def __str__(self) -> str:
        return f"{self.enrollment.student.matricule} — {self.year.label} — {self.average}"
