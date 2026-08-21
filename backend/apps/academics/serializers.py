"""Serialiseurs de la structure pedagogique."""

from __future__ import annotations

from rest_framework import serializers

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    Section,
    Semester,
    Subject,
    TeachingAssignment,
)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "label", "start_date", "end_date", "is_active"]

    def validate(self, attrs: dict) -> dict:
        debut = attrs.get("start_date", getattr(self.instance, "start_date", None))
        fin = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if debut and fin and fin <= debut:
            raise serializers.ValidationError(
                {"end_date": "تاريخ النهاية يجب أن يكون بعد تاريخ البداية."}
            )
        return attrs


class SemesterSerializer(serializers.ModelSerializer):
    year_label = serializers.CharField(source="year.label", read_only=True)
    state_display = serializers.CharField(source="get_state_display", read_only=True)
    current_session_display = serializers.CharField(
        source="get_current_session_display", read_only=True
    )

    class Meta:
        model = Semester
        fields = [
            "id",
            "year",
            "year_label",
            "number",
            "start_date",
            "end_date",
            "state",
            "state_display",
            "current_session",
            "current_session_display",
            "weight",
            "published_at",
        ]
        # L'etat ne se modifie que par les actions dediees, qui portent les
        # regles de transition et le recalcul.
        read_only_fields = ["state", "current_session", "published_at"]


class SectionSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Section
        fields = ["id", "code", "name_ar", "display_order", "is_active", "student_count"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "code", "name_ar", "display_order", "is_active"]


class CurriculumSerializer(serializers.ModelSerializer):
    """
    Programme : c'est ici que la matiere est liee au فصل avec son coefficient.
    """

    section_name = serializers.CharField(source="section.name_ar", read_only=True)
    subject_name = serializers.CharField(source="subject.name_ar", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    semester_number = serializers.IntegerField(source="semester.number", read_only=True)

    class Meta:
        model = Curriculum
        fields = [
            "id",
            "section",
            "section_name",
            "semester",
            "semester_number",
            "subject",
            "subject_code",
            "subject_name",
            "coefficient",
            "display_order",
            "is_active",
        ]

    def validate_coefficient(self, value):
        if value <= 0:
            raise serializers.ValidationError("الضارب يجب أن يكون أكبر من صفر.")
        return value


class EnrollmentSerializer(serializers.ModelSerializer):
    matricule = serializers.CharField(source="student.matricule", read_only=True)
    full_name_ar = serializers.CharField(source="student.full_name_ar", read_only=True)
    section_name = serializers.CharField(source="section.name_ar", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "matricule",
            "full_name_ar",
            "section",
            "section_name",
            "year",
            "is_active",
        ]


class TeachingAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name_ar", read_only=True)
    subject_name = serializers.CharField(
        source="curriculum.subject.name_ar", read_only=True
    )
    section_name = serializers.CharField(
        source="curriculum.section.name_ar", read_only=True
    )

    class Meta:
        model = TeachingAssignment
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "curriculum",
            "subject_name",
            "section_name",
            "is_active",
        ]


class DuplicationAnneeSerializer(serializers.Serializer):
    """
    Ouverture de l'annee suivante a partir d'une annee existante.

    On recopie la structure — فصول, programmes, coefficients — mais jamais les
    notes ni les resultats : une nouvelle annee part d'une page blanche.
    """

    label = serializers.CharField(max_length=20)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    activer = serializers.BooleanField(default=False)

    def validate_label(self, value: str) -> str:
        if AcademicYear.objects.filter(label=value).exists():
            raise serializers.ValidationError("هذه السنة الدراسية موجودة أصلا.")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["end_date"] <= attrs["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "تاريخ النهاية يجب أن يكون بعد تاريخ البداية."}
            )
        return attrs


class ReinscriptionSerializer(serializers.Serializer):
    """
    Reinscription en lot dans l'annee suivante.

    La section de destination est choisie par l'administration : aucun
    parcours automatique n'est suppose entre les اقسام.
    """

    year = serializers.IntegerField()
    section = serializers.IntegerField()
    students = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=500
    )
