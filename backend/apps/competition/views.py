"""
API du concours.

Deux publics, deux regimes. Le jury est authentifie et porte la permission
`competition.animer` ; l'ecran de la salle n'est personne et ne peut que lire.

L'ecran public est la seule route ouverte de toute l'application. Elle ne rend
donc que ce qui est destine a etre projete : les groupes, les scores, le tour
en cours. Aucune question a venir, aucun nom d'utilisateur, aucun identifiant
interne exploitable.
"""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.rbac import Permission
from apps.common.permissions import IsAdmin, RequiresPermission
from apps.competition import services
from apps.competition.models import (
    Competition,
    CompetitionState,
    Question,
    Turn,
)
from apps.competition.serializers import (
    CompetitionSerializer,
    DeciderSerializer,
    GroupSerializer,
    LancerSerializer,
    QuestionSerializer,
    QuestionsEnLotSerializer,
    TurnSerializer,
)

audit = logging.getLogger("asleyn.audit")

PeutAnimer = RequiresPermission(Permission.COMPETITION_ANIMER)


class CompetitionViewSet(viewsets.ModelViewSet):
    """Preparation et conduite d'un concours."""

    serializer_class = CompetitionSerializer
    permission_classes = [PeutAnimer]
    queryset = Competition.objects.prefetch_related("groups", "questions")

    def get_permissions(self):
        """
        La suppression est reservee a l'administration.

        Animer une session et en effacer une ne sont pas le meme geste : le
        premier se rattrape, le second emporte les groupes, les tours et les
        decisions du jury — c'est-a-dire la seule trace de ce qui s'est passe
        dans la salle. Une permission deleguee au jury ouvrirait cette porte a
        qui n'a besoin que de conduire un concours.
        """
        if self.action == "destroy":
            return [IsAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer) -> None:
        serializer.save(
            created_by=self.request.user, code=services.generer_code()
        )

    def perform_destroy(self, instance: Competition) -> None:
        audit.warning(
            "Concours supprime — %s (%s) : %d groupes, %d tours, par %s",
            instance.name,
            instance.code,
            instance.groups.count(),
            instance.turns.count(),
            self.request.user.username,
        )
        instance.delete()

    # ─── Preparation ───────────────────────────────────────────────

    @extend_schema(request=GroupSerializer, responses={201: GroupSerializer})
    @action(detail=True, methods=["post"], url_path="groupes")
    def ajouter_groupe(self, request: Request, pk=None) -> Response:
        competition = self.get_object()
        if competition.state != CompetitionState.DRAFT:
            raise ValidationError("لا يمكن تعديل المجموعات بعد انطلاق المسابقة.")

        serializer = GroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            competition=competition,
            display_order=serializer.validated_data.get(
                "display_order", competition.groups.count()
            ),
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=QuestionsEnLotSerializer, responses={201: QuestionSerializer(many=True)}
    )
    @action(detail=True, methods=["post"], url_path="questions")
    def ajouter_questions(self, request: Request, pk=None) -> Response:
        competition = self.get_object()
        if competition.state != CompetitionState.DRAFT:
            raise ValidationError("لا يمكن تعديل الأسئلة بعد انطلاق المسابقة.")
        if not competition.avec_questions:
            raise ValidationError("الندوة الشعرية لا تتضمن أسئلة.")

        serializer = QuestionsEnLotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        depart = competition.questions.count()
        creees = Question.objects.bulk_create(
            [
                Question(competition=competition, text=texte, display_order=depart + i)
                for i, texte in enumerate(serializer.validated_data["textes"])
            ]
        )
        return Response(
            QuestionSerializer(creees, many=True).data, status=status.HTTP_201_CREATED
        )

    # ─── Conduite ──────────────────────────────────────────────────

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"])
    def demarrer(self, request: Request, pk=None) -> Response:
        competition = self.get_object()
        try:
            total = services.demarrer(competition)
        except services.CompetitionInvalide as erreur:
            raise ValidationError(str(erreur)) from erreur

        audit.info(
            "Concours demarre — %s : %d tours, par %s",
            competition.name,
            total,
            request.user.username,
        )
        return Response({"tours": total, "code": competition.code})

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"])
    def deroule(self, request: Request, pk=None) -> Response:
        """
        Le deroule complet, pour la console du jury.

        Tout part en une fois — tours, groupes, enonces — parce que la suite
        peut se passer sans reseau. `maintenant` accompagne l'envoi : le
        navigateur en deduit son ecart avec le serveur, et son compte a rebours
        reste juste meme si l'horloge de la tablette ne l'est pas.
        """
        competition = self.get_object()
        tours = competition.turns.select_related("group", "question").all()
        return Response(
            {
                "competition": CompetitionSerializer(competition).data,
                "maintenant": timezone.now(),
                "tours": TurnSerializer(tours, many=True).data,
                "classement": services.classement(competition),
            }
        )

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"])
    def cloturer(self, request: Request, pk=None) -> Response:
        competition = services.cloturer(self.get_object())
        audit.info(
            "Concours cloture — %s par %s", competition.name, request.user.username
        )
        return Response(CompetitionSerializer(competition).data)


class LancerTourView(APIView):
    """Met le chronometre d'un tour en marche."""

    permission_classes = [PeutAnimer]

    @extend_schema(request=LancerSerializer, responses={200: TurnSerializer})
    def post(self, request: Request, pk: int) -> Response:
        tour = get_object_or_404(Turn.objects.select_related("competition"), pk=pk)
        serializer = LancerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.lancer_tour(
            tour,
            client_uuid=serializer.validated_data["client_uuid"],
            demarre_a=serializer.validated_data.get("demarre_a"),
        )
        tour.refresh_from_db()
        return Response(TurnSerializer(tour).data)


class DeciderTourView(APIView):
    """Enregistre la decision du jury sur un tour."""

    permission_classes = [PeutAnimer]

    @extend_schema(request=DeciderSerializer, responses={200: TurnSerializer})
    def post(self, request: Request, pk: int) -> Response:
        tour = get_object_or_404(
            Turn.objects.select_related("competition", "group"), pk=pk
        )
        serializer = DeciderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.trancher(
            tour,
            outcome=serializer.validated_data["outcome"],
            client_uuid=serializer.validated_data["client_uuid"],
            par=request.user,
            decide_a=serializer.validated_data.get("decide_a"),
            note=serializer.validated_data.get("note", ""),
        )
        tour.refresh_from_db()

        if tour.awarded_late:
            audit.info(
                "Point accorde hors delai — %s / %s par %s — %s",
                tour.competition.name,
                tour.group.name,
                request.user.username,
                tour.note or "sans motif",
            )
        return Response(TurnSerializer(tour).data)


class EcranPublicView(APIView):
    """
    Ce que la salle voit, sans connexion.

    Seule route ouverte de l'application. Elle ne rend donc que ce qui est fait
    pour etre projete — et rien de plus : ni les questions a venir, ni qui a
    tranche, ni les identifiants internes des tours.

    Son debit est compte a part : un ecran qui interroge toutes les deux
    secondes epuiserait en une minute le plafond des visiteurs anonymes.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "direct"

    @extend_schema(responses={200: None})
    def get(self, request: Request, code: str) -> Response:
        competition = get_object_or_404(
            Competition.objects.prefetch_related("groups"), code=code.upper()
        )
        courant = services.tour_courant(competition)
        maintenant = timezone.now()

        tour = None
        if courant is not None and competition.en_cours:
            tour = {
                "index": courant.index,
                "round_number": courant.round_number,
                "group_name": courant.group.name,
                "group_color": courant.group.color,
                "question_text": (
                    courant.question.text
                    if courant.question_id and competition.show_question
                    else None
                ),
                "started_at": courant.started_at,
                "secondes_restantes": courant.secondes_restantes(maintenant),
                "en_marche": courant.started_at is not None,
            }

        return Response(
            {
                "name": competition.name,
                "kind": competition.kind,
                "kind_display": competition.get_kind_display(),
                "state": competition.state,
                "state_display": competition.get_state_display(),
                "turn_seconds": competition.turn_seconds,
                "maintenant": maintenant,
                # `null` pour une ندوة شعرية : elle n'a pas de dernier tour
                # ecrit d'avance, et annoncer la reserve preparee ferait
                # croire a la salle qu'on en est au dixieme sur septante-cinq.
                "tours_prevus": (
                    competition.turns.count() if competition.avec_questions else None
                ),
                "tours_joues": competition.turns.exclude(outcome="PENDING").count(),
                "tour": tour,
                "classement": services.classement(competition),
            }
        )
