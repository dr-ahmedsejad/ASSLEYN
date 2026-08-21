"""Serialiseurs d'authentification et de profil."""

from __future__ import annotations

from django.contrib.auth import authenticate, password_validation
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Student, Teacher, User


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
    Authentification.

    `authenticate` recoit la requete : c'est indispensable pour que
    django-axes puisse comptabiliser les echecs et verrouiller le compte.
    """

    username = serializers.CharField(write_only=True, trim_whitespace=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    default_error_messages = {
        "invalid": "اسم المستخدم أو كلمة السر غير صحيحة.",
        "inactive": "هذا الحساب غير مفعل.",
    }

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = authenticate(
            request=request,
            username=attrs["username"],
            password=attrs["password"],
        )
        # Message unique : ne jamais reveler si le compte existe.
        if user is None:
            self.fail("invalid")
        if not user.is_active:
            self.fail("inactive")
        attrs["user"] = user
        return attrs


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
