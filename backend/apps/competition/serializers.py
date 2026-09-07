"""Serialiseurs du concours."""

from __future__ import annotations

from rest_framework import serializers

from apps.competition.models import Competition, Group, Question, Turn


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
    question_text = serializers.CharField(source="question.text", read_only=True)
    outcome_display = serializers.CharField(
        source="get_outcome_display", read_only=True
    )

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
    tours_prevus = serializers.IntegerField(read_only=True)
    nombre_groupes = serializers.SerializerMethodField()
    nombre_questions = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = [
            "id",
            "name",
            "code",
            "state",
            "state_display",
            "turn_seconds",
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
