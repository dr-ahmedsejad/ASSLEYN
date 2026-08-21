"""Serialiseurs des resultats calcules."""

from __future__ import annotations

from rest_framework import serializers

from apps.results.engine import round_for_display
from apps.results.models import AnnualResult, SemesterResult, SubjectResult


class SubjectResultSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(
        source="curriculum.subject.code", read_only=True
    )
    subject_name = serializers.CharField(
        source="curriculum.subject.name_ar", read_only=True
    )
    decision_display = serializers.CharField(
        source="get_decision_display", read_only=True
    )

    class Meta:
        model = SubjectResult
        fields = [
            "subject_code",
            "subject_name",
            "coefficient",
            "value",
            "normal_value",
            "resit_value",
            "effective_value",
            "decision",
            "decision_display",
        ]
        read_only_fields = fields


class SemesterResultSerializer(serializers.ModelSerializer):
    """
    Resultat d'un فصل.

    `average` est la valeur exacte utilisee pour le classement et les
    decisions ; `average_display` est celle qui figure sur le bulletin. Les
    deux sont exposees pour qu'aucune ambiguite d'arrondi ne subsiste.
    """

    matricule = serializers.CharField(
        source="enrollment.student.matricule", read_only=True
    )
    full_name_ar = serializers.CharField(
        source="enrollment.student.full_name_ar", read_only=True
    )
    section_name = serializers.CharField(
        source="enrollment.section.name_ar", read_only=True
    )
    semester_number = serializers.IntegerField(source="semester.number", read_only=True)
    session_display = serializers.CharField(
        source="get_session_display", read_only=True
    )
    pass_threshold = serializers.DecimalField(
        source="rule.pass_threshold", max_digits=5, decimal_places=2, read_only=True
    )
    average_display = serializers.SerializerMethodField()
    decision_display = serializers.CharField(
        source="get_decision_final_display", read_only=True
    )
    is_overridden = serializers.BooleanField(read_only=True)
    subject_results = SubjectResultSerializer(many=True, read_only=True)

    class Meta:
        model = SemesterResult
        fields = [
            "id",
            "matricule",
            "full_name_ar",
            "section_name",
            "semester",
            "semester_number",
            "session",
            "session_display",
            "pass_threshold",
            "average",
            "average_display",
            "total_coefficient",
            "rank",
            "cohort_size",
            "decision_computed",
            "decision_final",
            "decision_display",
            "is_overridden",
            "override_reason",
            "computed_at",
            "subject_results",
        ]
        read_only_fields = fields

    def get_average_display(self, obj: SemesterResult) -> str:
        return str(round_for_display(obj.average, obj.rule.rounding_decimals))


class AnnualResultSerializer(serializers.ModelSerializer):
    matricule = serializers.CharField(
        source="enrollment.student.matricule", read_only=True
    )
    full_name_ar = serializers.CharField(
        source="enrollment.student.full_name_ar", read_only=True
    )
    section_name = serializers.CharField(
        source="enrollment.section.name_ar", read_only=True
    )
    average_display = serializers.SerializerMethodField()
    decision_display = serializers.CharField(
        source="get_decision_final_display", read_only=True
    )

    class Meta:
        model = AnnualResult
        fields = [
            "id",
            "matricule",
            "full_name_ar",
            "section_name",
            "year",
            "average",
            "average_display",
            "rank",
            "cohort_size",
            "semester_count",
            "decision_computed",
            "decision_final",
            "decision_display",
            "override_reason",
            "computed_at",
        ]
        read_only_fields = fields

    def get_average_display(self, obj: AnnualResult) -> str:
        return str(round_for_display(obj.average))


class DecisionOverrideSerializer(serializers.Serializer):
    """
    Surcharge de la decision par le jury.

    Le motif est obligatoire : une decision qui s'ecarte du calcul doit
    pouvoir etre expliquee.
    """

    decision = serializers.ChoiceField(choices=["PASSED", "RESIT"])
    reason = serializers.CharField(max_length=255, allow_blank=False)

    def validate_reason(self, value: str) -> str:
        if len(value.strip()) < 5:
            raise serializers.ValidationError("السبب مختصر جدا.")
        return value.strip()


class RecomputeSerializer(serializers.Serializer):
    semester = serializers.IntegerField(required=False)
    section = serializers.IntegerField(required=False)
    session = serializers.CharField(required=False, allow_blank=True)
    annual = serializers.BooleanField(default=False)


class SeuilSectionSerializer(serializers.Serializer):
    """
    Seuils arretes en deliberation pour un قسم.

    La commission fixe la barre de reussite et, si elle le souhaite, le
    plancher de compensation. Laisser le plancher vide le fait suivre la
    barre : il ne peut jamais se retrouver au-dessus d'elle.
    """

    section = serializers.IntegerField()
    pass_threshold = serializers.DecimalField(max_digits=5, decimal_places=2)
    compensation_floor = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True, default=None
    )
    note = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )

    def validate_pass_threshold(self, value):
        if value <= 0:
            raise serializers.ValidationError("العتبة يجب أن تكون أكبر من صفر.")
        return value

    def validate_compensation_floor(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "الحد الأدنى للتعويض لا يمكن أن يكون سالبا."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        plancher = attrs.get("compensation_floor")
        if plancher is not None and plancher > attrs["pass_threshold"]:
            raise serializers.ValidationError(
                {
                    "compensation_floor": (
                        "الحد الأدنى للتعويض لا يمكن أن يتجاوز عتبة النجاح."
                    )
                }
            )
        return attrs
