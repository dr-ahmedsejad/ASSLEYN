"""
Comptes et identites.

Trois roles, un seul modele utilisateur. Le role est porte par le serveur et
n'est jamais deduit d'une donnee envoyee par le client.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.rbac import Permission, permissions_par_defaut


class Role(models.TextChoices):
    ADMIN = "ADMIN", _("مدير")
    ASSISTANT = "ASSISTANT", _("مساعد الإدارة")
    TEACHER = "TEACHER", _("أستاذ")
    STUDENT = "STUDENT", _("طالبة")


class User(AbstractUser):
    """Utilisateur unique de l'application, porteur du role."""

    role = models.CharField(
        _("الدور"), max_length=10, choices=Role.choices, default=Role.STUDENT
    )
    full_name_ar = models.CharField(_("الاسم الكامل"), max_length=150)
    phone = models.CharField(_("الهاتف"), max_length=30, blank=True)

    # Impose le changement de mot de passe a la premiere connexion : les
    # comptes etudiantes sont crees en lot avec un mot de passe temporaire.
    must_change_password = models.BooleanField(
        _("تغيير كلمة السر مطلوب"), default=False
    )
    password_changed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("مستخدم")
        verbose_name_plural = _("المستخدمون")
        indexes = [models.Index(fields=["role"])]

    def __str__(self) -> str:
        return f"{self.full_name_ar or self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN or self.is_superuser

    @property
    def is_assistant(self) -> bool:
        return self.role == Role.ASSISTANT

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT

    @property
    def is_staff_role(self) -> bool:
        """Personnel de l'institut : administration et assistance."""
        return self.is_admin_role or self.is_assistant

    def permissions_du_role(self) -> set[str]:
        """
        Permissions attachees au role.

        L'administration dispose de tout, par construction : aucune
        configuration ne peut la priver d'une capacite, sans quoi plus
        personne ne pourrait reparer le systeme.

        Pour les autres roles, si aucune attribution n'a encore ete
        enregistree — base fraiche, role ajoute recemment — on retombe sur les
        valeurs par defaut du catalogue plutot que de laisser l'utilisateur
        sans aucun droit.
        """
        if self.is_admin_role:
            return set(Permission.values)

        accordees = set(
            RolePermission.objects.filter(role=self.role).values_list(
                "permission", flat=True
            )
        )
        return accordees or set(permissions_par_defaut(self.role))

    def permissions(self) -> set[str]:
        """
        Permissions effectives : celles du role, corrigees des exceptions
        individuelles.

        Une exception permet de confier une capacite a une personne precise
        sans toucher a son role — par exemple la saisie des notes a un membre
        du personnel — ou de la lui retirer alors que son role la donne.
        """
        if self.is_admin_role:
            return set(Permission.values)

        effectives = self.permissions_du_role()
        for exception in UserPermission.objects.filter(user=self):
            if exception.granted:
                effectives.add(exception.permission)
            else:
                effectives.discard(exception.permission)
        return effectives

    def has_perm_code(self, code: str) -> bool:
        return code in self.permissions()


class RolePermission(models.Model):
    """
    Attribution d'une permission a un role.

    Le catalogue des permissions est fige dans le code (chaque code garde un
    endpoint reel) ; ce qui se configure, c'est qui en dispose.
    """

    role = models.CharField(_("الدور"), max_length=10, choices=Role.choices)
    permission = models.CharField(
        _("الصلاحية"), max_length=40, choices=Permission.choices
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="permissions_accordees",
        verbose_name=_("منحها"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("صلاحية دور")
        verbose_name_plural = _("صلاحيات الأدوار")
        ordering = ["role", "permission"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="une_permission_par_role",
            )
        ]

    def __str__(self) -> str:
        return f"{self.role} → {self.permission}"


class UserPermission(models.Model):
    """
    Exception individuelle : une capacite accordee ou retiree a une personne,
    quel que soit son role.

    `granted` a False est aussi utile que True : il permet de retirer a
    quelqu'un un droit que son role accorde, sans creer un role de plus.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="permission_exceptions",
        verbose_name=_("المستخدم"),
    )
    permission = models.CharField(
        _("الصلاحية"), max_length=40, choices=Permission.choices
    )
    granted = models.BooleanField(_("ممنوحة"), default=True)
    reason = models.CharField(_("السبب"), max_length=255, blank=True)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exceptions_accordees",
        verbose_name=_("قررها"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("صلاحية فردية")
        verbose_name_plural = _("الصلاحيات الفردية")
        ordering = ["user", "permission"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "permission"],
                name="une_exception_par_utilisateur_et_permission",
            )
        ]

    def __str__(self) -> str:
        signe = "+" if self.granted else "-"
        return f"{self.user.username} {signe}{self.permission}"


matricule_validator = RegexValidator(
    r"^\d{5}$", _("رقم الطالبة يتكون من خمسة أرقام.")
)


class Student(models.Model):
    """Etudiante. Le matricule est l'identifiant officiel de l'institut."""

    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name="student_profile",
        null=True,
        blank=True,
        verbose_name=_("الحساب"),
    )
    # unique=True au niveau base : l'anomalie du matricule 24097 attribue a
    # deux etudiantes differentes devient structurellement impossible.
    matricule = models.CharField(
        _("رقم الطالبة"),
        max_length=10,
        unique=True,
        validators=[matricule_validator],
    )
    full_name_ar = models.CharField(_("الاسم الكامل"), max_length=150)
    birth_date = models.DateField(_("تاريخ الميلاد"), null=True, blank=True)
    guardian_name = models.CharField(_("اسم الولي"), max_length=150, blank=True)
    guardian_phone = models.CharField(_("هاتف الولي"), max_length=30, blank=True)
    is_active = models.BooleanField(_("نشطة"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("طالبة")
        verbose_name_plural = _("الطالبات")
        ordering = ["matricule"]

    def __str__(self) -> str:
        return f"{self.matricule} — {self.full_name_ar}"


class Teacher(models.Model):
    """Enseignant."""

    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name="teacher_profile",
        verbose_name=_("الحساب"),
    )
    full_name_ar = models.CharField(_("الاسم الكامل"), max_length=150)
    phone = models.CharField(_("الهاتف"), max_length=30, blank=True)
    is_active = models.BooleanField(_("نشط"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("أستاذ")
        verbose_name_plural = _("الأساتذة")
        ordering = ["full_name_ar"]

    def __str__(self) -> str:
        return self.full_name_ar


class LoginOutcome(models.TextChoices):
    """Issue d'une tentative de connexion."""

    SUCCESS = "SUCCESS", _("نجاح")
    BAD_PASSWORD = "BAD_PASSWORD", _("كلمة سر خاطئة")
    UNKNOWN_USER = "UNKNOWN_USER", _("مستخدم غير معروف")
    INACTIVE = "INACTIVE", _("حساب معطل")
    LOCKED = "LOCKED", _("محاولة أثناء الإقفال")


class LoginAttempt(models.Model):
    """
    Journal des connexions — reussites comme echecs.

    Le nom d'utilisateur est conserve **tel qu'il a ete saisi**, meme s'il ne
    correspond a aucun compte : c'est precisement ce qu'on veut lire apres
    coup. Un lien vers `User` serait vide dans le cas le plus interessant.

    Ce journal est en ecriture seule du point de vue de l'application : rien
    ne le modifie, rien ne l'efface. Une trace qu'on peut retoucher ne prouve
    plus rien.
    """

    username = models.CharField(_("اسم المستخدم"), max_length=150, db_index=True)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_attempts",
        verbose_name=_("الحساب"),
    )
    outcome = models.CharField(
        _("النتيجة"), max_length=15, choices=LoginOutcome.choices, db_index=True
    )
    ip_address = models.GenericIPAddressField(_("عنوان IP"), null=True, blank=True)
    # Tronque : un agent utilisateur depasse parfois le kilo-octet, et seul son
    # debut identifie le navigateur.
    user_agent = models.CharField(_("المتصفح"), max_length=255, blank=True)
    at = models.DateTimeField(_("التاريخ"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("محاولة دخول")
        verbose_name_plural = _("سجل الدخول")
        ordering = ["-at"]
        indexes = [
            # Sert deux lectures chaudes : le decompte des echecs recents d'un
            # compte, et le classement des visiteuses.
            models.Index(fields=["username", "-at"], name="tentative_par_compte"),
            models.Index(fields=["outcome", "-at"], name="tentative_par_issue"),
        ]

    def __str__(self) -> str:
        return f"{self.username} — {self.outcome} — {self.at:%Y-%m-%d %H:%M}"

    @property
    def reussie(self) -> bool:
        return self.outcome == LoginOutcome.SUCCESS


class Lockout(models.Model):
    """
    Periode de blocage d'un compte apres des echecs repetes.

    Le blocage porte sur le **nom d'utilisateur**, pas sur l'adresse IP : c'est
    ce que demande l'etablissement, et c'est aussi ce qui protege une etudiante
    dont le mot de passe est essaye depuis plusieurs reseaux. Le revers est
    connu : quelqu'un qui connait un identifiant peut en bloquer l'acces a
    repetition. D'ou l'ecran de deblocage — l'administration rouvre en un
    geste, sans attendre l'expiration.
    """

    username = models.CharField(_("اسم المستخدم"), max_length=150, db_index=True)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lockouts",
        verbose_name=_("الحساب"),
    )
    #: 1, 2, 3 — le palier atteint, qui determine la duree.
    level = models.PositiveSmallIntegerField(_("المستوى"), default=1)
    started_at = models.DateTimeField(_("بداية الإقفال"), auto_now_add=True)
    until = models.DateTimeField(_("نهاية الإقفال"), db_index=True)
    ip_address = models.GenericIPAddressField(_("عنوان IP"), null=True, blank=True)
    released_at = models.DateTimeField(_("تاريخ الفتح"), null=True, blank=True)
    released_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lockouts_released",
        verbose_name=_("فتحه"),
    )

    class Meta:
        verbose_name = _("إقفال حساب")
        verbose_name_plural = _("الحسابات المقفلة")
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.username} — niveau {self.level} jusqu'a {self.until:%H:%M}"

    @property
    def libere(self) -> bool:
        return self.released_at is not None
