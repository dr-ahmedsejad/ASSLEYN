"""Serialiseurs du concours."""

from __future__ import annotations

from rest_framework import serializers

from apps.competition.models import (
    Competition,
    CompetitionState,
    Group,
    Question,
    Turn,
)


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name", "display_order", "color"]


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "text", "display_order"]


class QuestionsEnLotSerializer(serializers.Serializer):
    """
    Saisie de plusieurs questions d'un coup.

    Les questions se preparent ailleurs — un document, un cahier — puis se
    collent ici. Les faire saisir une par une dans un formulaire serait le
    meilleur moyen de decourager l'usage.
    """

    textes = serializers.ListField(
        child=serializers.CharField(allow_blank=False, trim_whitespace=True),
        allow_empty=False,
    )


class TurnSerializer(serializers.ModelSerializer):
    """
    Un tour, tel que la console du jury en a besoin.

    Elle recoit le deroule **entier** au chargement : chaque tour porte donc
    son groupe et son enonce, et non de simples identifiants a resoudre par
    une requete supplementaire. Hors ligne, il n'y aura pas de seconde requete.
    """

    group_name = serializers.CharField(source="group.name", read_only=True)
    group_color = serializers.CharField(source="group.color", read_only=True)
    outcome_display = serializers.CharField(
        source="get_outcome_display", read_only=True
    )

    #: `null` pour une ندوة شعرية, ou le tour n'a pas d'enonce. Une source
    #: pointant sur `question.text` leverait sur ce tour-la.
    question_text = serializers.SerializerMethodField()

    def get_question_text(self, obj: Turn) -> str | None:
        return obj.question.text if obj.question_id else None

    class Meta:
        model = Turn
        fields = [
            "id",
            "index",
            "round_number",
            "group",
            "group_name",
            "group_color",
            "question",
            "question_text",
            "started_at",
            "outcome",
            "outcome_display",
            "decided_at",
            "awarded_late",
            "note",
        ]
        read_only_fields = fields


class CompetitionSerializer(serializers.ModelSerializer):
    groups = GroupSerializer(many=True, read_only=True)
    questions = QuestionSerializer(many=True, read_only=True)
    state_display = serializers.CharField(source="get_state_display", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    avec_questions = serializers.BooleanField(read_only=True)
    tours_prevus = serializers.IntegerField(read_only=True)
    nombre_groupes = serializers.SerializerMethodField()
    nombre_questions = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = [
            "id",
            "name",
            "kind",
            "kind_display",
            "avec_questions",
            "code",
            "state",
            "state_display",
            "turn_seconds",
            "rounds",
            "show_question",
            "created_at",
            "started_at",
            "finished_at",
            "tours_prevus",
            "nombre_groupes",
            "nombre_questions",
            "groups",
            "questions",
        ]
        read_only_fields = [
            "code",
            "state",
            "created_at",
            "started_at",
            "finished_at",
        ]

    def get_nombre_groupes(self, obj: Competition) -> int:
        return obj.groups.count()

    def get_nombre_questions(self, obj: Competition) -> int:
        return obj.questions.count()

    def validate(self, attrs: dict) -> dict:
        """
        Le type et le nombre de جولات se figent au demarrage.

        Les tours sont crees d'un coup a ce moment-la ; les changer ensuite ne
        changerait plus le deroule, mais ferait mentir ce qui est affiche.
        """
        instance = self.instance
        if instance is None or instance.state == CompetitionState.DRAFT:
            return attrs
        for champ in ("kind", "rounds"):
            if champ in attrs and attrs[champ] != getattr(instance, champ):
                raise serializers.ValidationError(
                    {champ: "لا يمكن تغيير هذا بعد انطلاق المسابقة."}
                )
        return attrs


class GesteSerializer(serializers.Serializer):
    """
    Base des gestes du jury.

    `client_uuid` est tire par le navigateur, avant l'envoi. C'est lui qui rend
    le rejeu inoffensif : la tablette peut vider sa file d'attente deux fois
    sans que le tour reparte ou que le point se dedouble.

    L'heure, elle aussi, vient du navigateur. Un geste rejoue apres une
    coupure garderait sinon l'heure de sa reception, et le retard du reseau se
    transformerait en depassement du temps de reponse.
    """

    client_uuid = serializers.UUIDField()


class LancerSerializer(GesteSerializer):
    demarre_a = serializers.DateTimeField(required=False, allow_null=True)


class DeciderSerializer(GesteSerializer):
    outcome = serializers.ChoiceField(choices=["CORRECT", "NO_ANSWER"])
    decide_a = serializers.DateTimeField(required=False, allow_null=True)
    note = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )
