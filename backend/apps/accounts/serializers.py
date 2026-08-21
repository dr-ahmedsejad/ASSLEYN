"""Serialiseurs d'authentification et de profil."""

from __future__ import annotations

from django.contrib.auth import password_validation
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Lockout, LoginAttempt, Student, Teacher, User


def nom_affiche(user: User | None) -> str:
    """Nom arabe d'un compte, ou chaine vide s'il n'y en a pas."""
    return user.full_name_ar if user else ""


class UserSerializer(serializers.ModelSerializer):
    """Profil renvoye au front. Ne contient aucune donnee sensible."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    matricule = serializers.SerializerMethodField()
    #: Capacites effectives : celles du role, corrigees des exceptions
    #: individuelles. Le front s'en sert pour construire la navigation.
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name_ar",
            "role",
            "role_display",
            "must_change_password",
            "matricule",
            "permissions",
        ]
        read_only_fields = fields

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(obj.permissions())

    def get_matricule(self, obj: User) -> str | None:
        student = getattr(obj, "student_profile", None)
        return student.matricule if student else None


class LoginSerializer(serializers.Serializer):
    """
    Identifiants soumis a la connexion.

    Ce serialiseur ne valide que la **forme**. L'authentification elle-meme
    appartient a la vue : elle doit, dans le meme mouvement, consulter l'etat
    de blocage du compte, inscrire la tentative au journal et decider du
    minuteur a renvoyer. Repartir cette decision entre deux couches la rendrait
    impossible a suivre.
    """

    username = serializers.CharField(write_only=True, trim_whitespace=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("كلمة السر الحالية غير صحيحة.")
        return value

    def validate_new_password(self, value: str) -> str:
        user = self.context["request"].user
        password_validation.validate_password(value, user)
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "كلمة السر الجديدة يجب أن تختلف عن الحالية."}
            )
        return attrs

    def save(self, **kwargs) -> User:
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.password_changed_at = timezone.now()
        user.save(
            update_fields=["password", "must_change_password", "password_changed_at"]
        )
        return user


class StudentSerializer(serializers.ModelSerializer):
    has_account = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "matricule",
            "full_name_ar",
            "birth_date",
            "guardian_name",
            "guardian_phone",
            "is_active",
            "has_account",
        ]

    def get_has_account(self, obj: Student) -> bool:
        return obj.user_id is not None


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = ["id", "full_name_ar", "phone", "is_active"]


class LoginAttemptSerializer(serializers.ModelSerializer):
    """Une ligne du journal des connexions."""

    outcome_display = serializers.CharField(
        source="get_outcome_display", read_only=True
    )
    full_name_ar = serializers.SerializerMethodField()
    role = serializers.CharField(source="user.role", read_only=True, default=None)

    class Meta:
        model = LoginAttempt
        fields = [
            "id",
            "username",
            "full_name_ar",
            "role",
            "outcome",
            "outcome_display",
            "ip_address",
            "user_agent",
            "at",
        ]

    def get_full_name_ar(self, obj: LoginAttempt) -> str:
        """
        Nom lisible, quand le compte existe encore.

        Une tentative sur un identifiant inconnu n'a evidemment pas de nom :
        c'est le nom saisi qui fait foi, et il est deja dans `username`.
        """
        return nom_affiche(obj.user)


class LockoutSerializer(serializers.ModelSerializer):
    """Un blocage, actif ou clos."""

    full_name_ar = serializers.SerializerMethodField()
    actif = serializers.SerializerMethodField()
    secondes_restantes = serializers.SerializerMethodField()
    duree_minutes = serializers.SerializerMethodField()
    released_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Lockout
        fields = [
            "id",
            "username",
            "full_name_ar",
            "level",
            "duree_minutes",
            "started_at",
            "until",
            "ip_address",
            "actif",
            "secondes_restantes",
            "released_at",
            "released_by_name",
        ]

    def get_full_name_ar(self, obj: Lockout) -> str:
        return nom_affiche(obj.user)

    def get_actif(self, obj: Lockout) -> bool:
        return obj.released_at is None and obj.until > timezone.now()

    def get_secondes_restantes(self, obj: Lockout) -> int:
        if not self.get_actif(obj):
            return 0
        return max(int((obj.until - timezone.now()).total_seconds()), 0)

    def get_duree_minutes(self, obj: Lockout) -> int:
        # Arrondi, et non troncature : `started_at` est pose a l'insertion,
        # quelques millisecondes apres le calcul de `until`. Un plancher
        # afficherait « 4 minutes » pour un blocage de cinq.
        return round((obj.until - obj.started_at).total_seconds() / 60)

    def get_released_by_name(self, obj: Lockout) -> str:
        return nom_affiche(obj.released_by)


class ReinitialisationMotDePasseSerializer(serializers.Serializer):
    """
    Reinitialisation par l'administration.

    L'ancien mot de passe n'est pas demande : c'est tout l'objet de la
    manoeuvre — l'administration intervient precisement quand la personne ne
    le connait plus. Le nouveau mot de passe est temporaire, son remplacement
    est impose a la premiere connexion.
    """

    new_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
    )

    def validate_new_password(self, value: str) -> str:
        if not value:
            return value
        password_validation.validate_password(value, self.context["cible"])
        return value
