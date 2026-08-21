"""Serialiseurs de saisie des notes."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.grading.models import Grade, GradeHistory, GradeStatus, GradingRule


class GradingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingRule
        fields = [
            "id",
            "year",
            "section",
            "version",
            "max_grade",
            "pass_threshold",
            "compensation_floor",
            "ranking_mode",
            "absence_policy",
            "rounding_decimals",
            "is_active",
        ]

    def validate(self, attrs: dict) -> dict:
        def valeur(nom: str) -> Decimal:
            return attrs.get(nom, getattr(self.instance, nom, None))

        seuil, plancher, maxi = (
            valeur("pass_threshold"),
            valeur("compensation_floor"),
            valeur("max_grade"),
        )
        if plancher is not None and seuil is not None and plancher > seuil:
            raise serializers.ValidationError(
                {"compensation_floor": "الحد الأدنى للتعويض لا يمكن أن يتجاوز عتبة النجاح."}
            )
        if seuil is not None and maxi is not None and seuil > maxi:
            raise serializers.ValidationError(
                {"pass_threshold": "عتبة النجاح لا يمكن أن تتجاوز النقطة القصوى."}
            )
        return attrs


class GradeRowSerializer(serializers.Serializer):
    """Une ligne de la grille de saisie."""

    enrollment = serializers.IntegerField()
    matricule = serializers.CharField(read_only=True)
    full_name_ar = serializers.CharField(read_only=True)
    value = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False
    )
    status = serializers.ChoiceField(choices=GradeStatus.choices, required=False)
    updated_at = serializers.DateTimeField(read_only=True)


class GradeUpsertSerializer(serializers.Serializer):
    """
    Une note a enregistrer.

    Le couple (valeur, statut) est verifie ici : une note chiffree n'a de sens
    qu'avec le statut « مسجلة », et reciproquement.
    """

    enrollment = serializers.IntegerField()
    value = serializers.DecimalField(
        max_digits=5, decimal_places=2, allow_null=True, required=False, default=None
    )
    status = serializers.ChoiceField(
        choices=GradeStatus.choices, required=False, default=GradeStatus.ENTERED
    )
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )

    def validate(self, attrs: dict) -> dict:
        statut = attrs.get("status", GradeStatus.ENTERED)
        valeur = attrs.get("value")

        if statut == GradeStatus.ENTERED and valeur is None:
            raise serializers.ValidationError(
                {"value": "النقطة مطلوبة عند حالة « مسجلة »."}
            )
        if statut != GradeStatus.ENTERED and valeur is not None:
            raise serializers.ValidationError(
                {"value": "لا يمكن تسجيل نقطة مع حالة غير « مسجلة »."}
            )

        maxi: Decimal = self.context["max_grade"]
        if valeur is not None and not (Decimal("0") <= valeur <= maxi):
            raise serializers.ValidationError(
                {"value": f"النقطة يجب أن تكون بين 0 و {maxi}."}
            )
        return attrs


class BulkGradeSerializer(serializers.Serializer):
    """Enregistrement en lot d'une colonne de la grille."""

    curriculum = serializers.IntegerField()
    grades = GradeUpsertSerializer(many=True)

    def validate_grades(self, value: list[dict]) -> list[dict]:
        if not value:
            raise serializers.ValidationError("لا توجد نقاط لحفظها.")
        vus = [g["enrollment"] for g in value]
        if len(vus) != len(set(vus)):
            raise serializers.ValidationError("تكرار في قائمة الطالبات.")
        return value


class GradeSerializer(serializers.ModelSerializer):
    matricule = serializers.CharField(
        source="enrollment.student.matricule", read_only=True
    )
    full_name_ar = serializers.CharField(
        source="enrollment.student.full_name_ar", read_only=True
    )
    subject_name = serializers.CharField(
        source="curriculum.subject.name_ar", read_only=True
    )

    class Meta:
        model = Grade
        fields = [
            "id",
            "enrollment",
            "matricule",
            "full_name_ar",
            "curriculum",
            "subject_name",
            "value",
            "status",
            "updated_at",
        ]
        read_only_fields = fields


class GradeHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(
        source="changed_by.full_name_ar", read_only=True
    )
    matricule = serializers.CharField(
        source="grade.enrollment.student.matricule", read_only=True
    )
    full_name_ar = serializers.CharField(
        source="grade.enrollment.student.full_name_ar", read_only=True
    )
    subject_name = serializers.CharField(
        source="grade.curriculum.subject.name_ar", read_only=True
    )
    section_name = serializers.CharField(
        source="grade.curriculum.section.name_ar", read_only=True
    )

    class Meta:
        model = GradeHistory
        fields = [
            "id",
            "grade",
            "matricule",
            "full_name_ar",
            "subject_name",
            "section_name",
            "old_value",
            "new_value",
            "old_status",
            "new_status",
            "reason",
            "changed_by",
            "changed_by_name",
            "changed_at",
        ]
        read_only_fields = fields
