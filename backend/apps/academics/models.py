"""
Structure pedagogique : annee, فصل, section, matiere, programme.

Le coeur de ce module est `Curriculum` : c'est la table qui lie une matiere a
un فصل pour une section donnee, avec son coefficient. Tout le reste du systeme
en depend.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Student, Teacher


class AcademicYear(models.Model):
    """Annee scolaire, par exemple « 2025-2026 »."""

    label = models.CharField(_("السنة الدراسية"), max_length=20, unique=True)
    start_date = models.DateField(_("تاريخ البداية"))
    end_date = models.DateField(_("تاريخ النهاية"))
    is_active = models.BooleanField(_("السنة الجارية"), default=False)

    class Meta:
        verbose_name = _("سنة دراسية")
        verbose_name_plural = _("السنوات الدراسية")
        ordering = ["-start_date"]
        constraints = [
            # Une seule annee active a la fois : evite toute ambiguite sur
            # « l'annee en cours » dans les ecrans et les calculs.
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="une_seule_annee_active",
            )
        ]

    def __str__(self) -> str:
        return self.label

    def clean(self) -> None:
        if self.end_date <= self.start_date:
            raise ValidationError(
                {"end_date": _("تاريخ النهاية يجب أن يكون بعد تاريخ البداية.")}
            )


class ExamSession(models.TextChoices):
    """
    Les deux sessions d'examen d'un فصل.

    La session de rattrapage ne concerne que les etudiantes declarees
    استدراك a l'issue de la session normale, et seulement dans les matieres
    ou elles ont ete jugees غير مستوفي.
    """

    NORMAL = "NORMAL", _("الدورة العادية")
    RESIT = "RESIT", _("الدورة الاستدراكية")


class SemesterState(models.TextChoices):
    """Cycle de vie d'un فصل. C'est ce qui gouverne les droits d'ecriture."""

    DRAFT = "DRAFT", _("مسودة")
    OPEN = "OPEN", _("مفتوح للإدخال")
    CLOSED = "CLOSED", _("مغلق")
    PUBLISHED = "PUBLISHED", _("منشور")


class Semester(models.Model):
    """
    فصل دراسي. L'institut en compte deux par annee.

    `weight` sert au calcul de la moyenne annuelle. Il vaut 1 pour les deux
    فصول (moyenne arithmetique), mais reste modifiable sans redeploiement si
    la direction change de regle.
    """

    year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="semesters",
        verbose_name=_("السنة الدراسية"),
    )
    number = models.PositiveSmallIntegerField(
        _("رقم الفصل"), validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    start_date = models.DateField(_("تاريخ البداية"))
    end_date = models.DateField(_("تاريخ النهاية"))
    state = models.CharField(
        _("الحالة"),
        max_length=10,
        choices=SemesterState.choices,
        default=SemesterState.DRAFT,
    )
    # Session en cours de saisie. Le فصل repasse par OPEN une seconde fois
    # pour la session de rattrapage, sans effacer la session normale.
    current_session = models.CharField(
        _("الدورة الجارية"),
        max_length=10,
        choices=ExamSession.choices,
        default=ExamSession.NORMAL,
    )
    weight = models.DecimalField(
        _("الوزن في المعدل السنوي"),
        max_digits=4,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0)],
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("فصل دراسي")
        verbose_name_plural = _("الفصول الدراسية")
        ordering = ["year", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "number"], name="fasl_unique_par_annee"
            )
        ]

    def __str__(self) -> str:
        return f"{self.year.label} — الفصل {self.number}"

    @property
    def accepts_grade_entry(self) -> bool:
        """Les notes ne s'ecrivent qu'en saisie ouverte."""
        return self.state == SemesterState.OPEN

    @property
    def resit_open(self) -> bool:
        return self.current_session == ExamSession.RESIT

    @property
    def is_visible_to_students(self) -> bool:
        return self.state == SemesterState.PUBLISHED


class Section(models.Model):
    """
    Section de l'institut (قسم).

    Chaque section a son propre programme : ce n'est pas un tronc commun.
    """

    code = models.SlugField(_("الرمز"), max_length=30, unique=True)
    name_ar = models.CharField(_("اسم القسم"), max_length=100, unique=True)
    display_order = models.PositiveSmallIntegerField(_("ترتيب العرض"), default=0)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("قسم")
        verbose_name_plural = _("الأقسام")
        ordering = ["display_order", "name_ar"]

    def __str__(self) -> str:
        return self.name_ar


class Subject(models.Model):
    """Matiere du catalogue global (النحو, الفقه, القرآن الكريم...)."""

    code = models.SlugField(_("الرمز"), max_length=30, unique=True)
    name_ar = models.CharField(_("اسم المادة"), max_length=100, unique=True)
    display_order = models.PositiveSmallIntegerField(_("ترتيب العرض"), default=0)
    is_active = models.BooleanField(_("نشطة"), default=True)

    class Meta:
        verbose_name = _("مادة")
        verbose_name_plural = _("المواد")
        ordering = ["display_order", "name_ar"]

    def __str__(self) -> str:
        return self.name_ar


class Curriculum(models.Model):
    """
    Programme : (section × فصل × matiere) → coefficient.

    C'est la table pivot demandee : elle lie les matieres au فصل. Le
    coefficient y est porte, et non sur la matiere, parce qu'une meme matiere
    n'a pas le meme poids d'une section a l'autre — القرآن الكريم vaut 5 chez
    المربيات et 5 chez المتميزات mais sur un total de coefficients different.
    """

    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        related_name="curricula",
        verbose_name=_("القسم"),
    )
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="curricula",
        verbose_name=_("الفصل"),
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="curricula",
        verbose_name=_("المادة"),
    )
    coefficient = models.DecimalField(
        _("الضارب"),
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_active = models.BooleanField(_("نشط"), default=True)
    display_order = models.PositiveSmallIntegerField(_("ترتيب العرض"), default=0)

    class Meta:
        verbose_name = _("مادة الفصل")
        verbose_name_plural = _("مواد الفصول")
        ordering = ["section", "semester", "display_order", "subject"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "semester", "subject"],
                name="une_matiere_une_fois_par_section_et_fasl",
            )
        ]

    def __str__(self) -> str:
        return f"{self.section.name_ar} / {self.subject.name_ar} × {self.coefficient}"


class Enrollment(models.Model):
    """Inscription d'une etudiante dans une section pour une annee."""

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name=_("الطالبة"),
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name=_("القسم"),
    )
    year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name=_("السنة الدراسية"),
    )
    is_active = models.BooleanField(_("نشطة"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("تسجيل")
        verbose_name_plural = _("التسجيلات")
        ordering = ["year", "section", "student__matricule"]
        constraints = [
            # Une etudiante n'appartient qu'a une seule section par annee.
            models.UniqueConstraint(
                fields=["student", "year"], name="une_section_par_etudiante_et_annee"
            )
        ]

    def __str__(self) -> str:
        return f"{self.student.matricule} — {self.section.name_ar} ({self.year.label})"


class TeachingAssignment(models.Model):
    """Affectation d'un enseignant a une matiere d'un فصل pour une section."""

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name=_("الأستاذ"),
    )
    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name=_("مادة الفصل"),
    )
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("إسناد التدريس")
        verbose_name_plural = _("إسنادات التدريس")
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "curriculum"], name="une_affectation_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.teacher.full_name_ar} → {self.curriculum}"
