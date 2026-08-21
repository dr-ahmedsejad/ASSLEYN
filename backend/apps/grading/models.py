"""
Notes et reglement de notation.

Deux idees structurantes :

1. Le reglement (`GradingRule`) est une donnee versionnee, pas du code. Un
   resultat calcule garde la reference de la version de reglement utilisee, ce
   qui rend chaque bulletin reproductible des annees plus tard.

2. Une note distingue explicitement « absente » de « a eu zero » — distinction
   que le fichier Excel d'origine ne permettait pas.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    ExamSession,
    Section,
    Semester,
)


class RankingMode(models.TextChoices):
    """Deux conventions de classement possibles."""

    # 1, 2, 3, 3, 4 — convention effectivement utilisee par l'institut,
    # confirmee sur deux sections du fichier 2025-2026.
    DENSE = "DENSE", _("متتابع (1، 2، 3، 3، 4)")
    # 1, 2, 3, 3, 5 — convention sportive, laissee disponible.
    STANDARD = "STANDARD", _("تنافسي (1، 2، 3، 3، 5)")


class ResitPolicy(models.TextChoices):
    """Comment la note de rattrapage se combine a celle de la session normale."""

    BEST = "BEST", _("أعلى النقطتين")
    REPLACE = "REPLACE", _("تعوّض نقطة الدورة العادية")
    BEST_CAPPED = "BEST_CAPPED", _("أعلى النقطتين بسقف عتبة النجاح")


class AbsencePolicy(models.TextChoices):
    COUNT_AS_ZERO = "ZERO", _("تحتسب صفرا")
    EXCLUDE = "EXCLUDE", _("تستثنى من المعدل")


class GradingRule(models.Model):
    """
    Reglement de notation applicable a une annee, eventuellement restreint a
    une section.

    Valeurs par defaut = regles reconstituees depuis le fichier
    « Résultat Trimestre 1 - A2 - 2025-2026.xlsx » et validees sur 98 lignes.
    """

    year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="grading_rules",
        verbose_name=_("السنة الدراسية"),
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="grading_rules",
        null=True,
        blank=True,
        help_text=_("اتركه فارغا لتطبيق القاعدة على جميع الأقسام."),
        verbose_name=_("القسم"),
    )
    # Un seuil arrete en deliberation ne vaut que pour ce فصل : laisser vide
    # pour une regle valable toute l'annee.
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="grading_rules",
        null=True,
        blank=True,
        help_text=_("اتركه فارغا لتطبيق القاعدة على كل فصول السنة."),
        verbose_name=_("الفصل"),
    )
    version = models.PositiveSmallIntegerField(_("رقم النسخة"), default=1)

    max_grade = models.DecimalField(
        _("النقطة القصوى"), max_digits=5, decimal_places=2, default=20
    )
    pass_threshold = models.DecimalField(
        _("عتبة النجاح"), max_digits=5, decimal_places=2, default=10
    )
    compensation_floor = models.DecimalField(
        _("الحد الأدنى للتعويض"), max_digits=5, decimal_places=2, default=7
    )
    ranking_mode = models.CharField(
        _("طريقة الترتيب"),
        max_length=10,
        choices=RankingMode.choices,
        default=RankingMode.DENSE,
    )
    absence_policy = models.CharField(
        _("معاملة الغياب"),
        max_length=10,
        choices=AbsencePolicy.choices,
        default=AbsencePolicy.COUNT_AS_ZERO,
    )
    rounding_decimals = models.PositiveSmallIntegerField(_("عدد الأرقام العشرية"), default=2)
    resit_policy = models.CharField(
        _("احتساب نقطة الاستدراك"),
        max_length=15,
        choices=ResitPolicy.choices,
        default=ResitPolicy.BEST,
    )

    is_active = models.BooleanField(_("نشط"), default=True)
    # Trace de la deliberation : qui a arrete ce seuil, et quand.
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="grading_rules_created",
        verbose_name=_("أقرّها"),
    )
    note = models.CharField(_("ملاحظة المداولة"), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("قاعدة التقويم")
        verbose_name_plural = _("قواعد التقويم")
        ordering = ["year", "section", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "section", "semester", "version"],
                name="version_unique_par_annee_section_et_fasl",
            )
        ]

    def __str__(self) -> str:
        cible = self.section.name_ar if self.section else _("كل الأقسام")
        portee = f" — الفصل {self.semester.number}" if self.semester_id else ""
        return f"{self.year.label} — {cible}{portee} — v{self.version}"

    def clean(self) -> None:
        if self.compensation_floor > self.pass_threshold:
            raise ValidationError(
                {
                    "compensation_floor": _(
                        "الحد الأدنى للتعويض لا يمكن أن يتجاوز عتبة النجاح."
                    )
                }
            )
        if self.pass_threshold > self.max_grade:
            raise ValidationError(
                {"pass_threshold": _("عتبة النجاح لا يمكن أن تتجاوز النقطة القصوى.")}
            )


class GradeStatus(models.TextChoices):
    ENTERED = "ENTERED", _("مسجلة")
    ABSENT = "ABSENT", _("غائبة")
    ABSENT_EXCUSED = "EXCUSED", _("غياب مبرر")
    EXEMPT = "EXEMPT", _("معفاة")
    MISSING = "MISSING", _("لم تدخل بعد")


class Grade(models.Model):
    """
    Note d'une etudiante dans une matiere d'un فصل.

    `value` est nul des que le statut n'est pas « mesuree » : c'est le statut,
    et non une valeur conventionnelle, qui porte le sens.
    """

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="grades",
        verbose_name=_("التسجيل"),
    )
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="grades",
        verbose_name=_("مادة الفصل"),
    )
    value = models.DecimalField(
        _("النقطة"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    session = models.CharField(
        _("الدورة"),
        max_length=10,
        choices=ExamSession.choices,
        default=ExamSession.NORMAL,
    )
    status = models.CharField(
        _("الحالة"),
        max_length=10,
        choices=GradeStatus.choices,
        default=GradeStatus.MISSING,
    )
    entered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="grades_entered",
        null=True,
        blank=True,
        verbose_name=_("أدخلها"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("نقطة")
        verbose_name_plural = _("النقاط")
        ordering = ["enrollment", "curriculum"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "curriculum", "session"],
                name="une_note_par_etudiante_matiere_et_dorra",
            ),
            # Une note chiffree n'existe que pour le statut « mesuree », et
            # reciproquement. Contrainte posee en base, pas seulement en code.
            models.CheckConstraint(
                condition=(
                    models.Q(status="ENTERED", value__isnull=False)
                    | (~models.Q(status="ENTERED") & models.Q(value__isnull=True))
                ),
                name="valeur_coherente_avec_statut",
            ),
        ]
        indexes = [models.Index(fields=["curriculum", "session", "status"])]

    def __str__(self) -> str:
        affichage = self.value if self.value is not None else self.get_status_display()
        return f"{self.enrollment.student.matricule} / {self.curriculum.subject.name_ar} = {affichage}"

    def clean(self) -> None:
        if self.status == GradeStatus.ENTERED and self.value is None:
            raise ValidationError({"value": _("النقطة مطلوبة عند حالة « مسجلة ».")})
        if self.status != GradeStatus.ENTERED and self.value is not None:
            raise ValidationError(
                {"value": _("لا يمكن تسجيل نقطة مع حالة غير « مسجلة ».")}
            )
        if not self.curriculum.semester.accepts_grade_entry:
            raise ValidationError(
                _("الفصل غير مفتوح لإدخال النقاط.")
            )
        if self.enrollment.section_id != self.curriculum.section_id:
            raise ValidationError(
                _("المادة لا تنتمي إلى قسم الطالبة.")
            )


class GradeHistory(models.Model):
    """
    Journal immuable des ecritures de notes.

    Rien n'est jamais supprime ni modifie ici : c'est la piece qui permet de
    repondre a « qui a change cette note, quand, et pourquoi ».
    """

    grade = models.ForeignKey(
        Grade, on_delete=models.CASCADE, related_name="history", verbose_name=_("النقطة")
    )
    old_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    new_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    old_status = models.CharField(max_length=10, blank=True)
    new_status = models.CharField(max_length=10)
    session = models.CharField(
        _("الدورة"), max_length=10, choices=ExamSession.choices, default=ExamSession.NORMAL
    )
    reason = models.CharField(_("السبب"), max_length=255, blank=True)
    changed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="grade_changes",
        verbose_name=_("غيّرها"),
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("سجل تغيير النقطة")
        verbose_name_plural = _("سجل تغييرات النقاط")
        ordering = ["-changed_at"]
        indexes = [models.Index(fields=["grade", "-changed_at"])]

    def __str__(self) -> str:
        return f"{self.grade_id}: {self.old_value} → {self.new_value}"
