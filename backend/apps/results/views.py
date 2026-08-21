"""
Consultation et pilotage des resultats.

Point de vigilance : une etudiante ne voit ses resultats que si le فصل est
publie. Ce filtre est applique dans `get_queryset`, donc il tient meme si
l'identifiant est devine.
"""

from __future__ import annotations

import logging

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import AcademicYear, Section, Semester, SemesterState
from apps.academics.views import sections_visibles
from apps.common.permissions import PeutDeliberer
from apps.results.models import AnnualResult, SemesterResult
from apps.results.serializers import (
    AnnualResultSerializer,
    DecisionOverrideSerializer,
    RecomputeSerializer,
    SemesterResultSerializer,
)
from apps.results.services import (
    recompute_annual,
    recompute_semester,
    recompute_semester_all_sections,
)

audit = logging.getLogger("asleyn.audit")


class SemesterResultViewSet(viewsets.ReadOnlyModelViewSet):
    """Resultats d'un فصل."""

    serializer_class = SemesterResultSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = [
        "semester",
        "session",
        "enrollment",
        "enrollment__section",
        "decision_final",
    ]
    queryset = SemesterResult.objects.none()
    ordering_fields = ["rank", "average"]

    def get_queryset(self) -> QuerySet[SemesterResult]:
        user = self.request.user
        base = SemesterResult.objects.select_related(
            "enrollment__student", "enrollment__section", "semester", "rule"
        ).prefetch_related("subject_results__curriculum__subject")

        if user.is_student:
            # Ses propres resultats, et seulement une fois publies. Les deux
            # sessions restent visibles : la session normale explique la
            # convocation au rattrapage.
            return base.filter(
                enrollment__student__user=user,
                semester__state=SemesterState.PUBLISHED,
            )
        return base.filter(enrollment__section__in=sections_visibles(user))

    @extend_schema(
        request=DecisionOverrideSerializer, responses={200: SemesterResultSerializer}
    )
    @action(detail=True, methods=["post"], permission_classes=[PeutDeliberer])
    def override(self, request: Request, pk: str | None = None) -> Response:
        """
        Surcharge de la decision par le conseil de section.

        Le calcul n'est pas efface : `decision_computed` reste visible a cote
        de la decision retenue, avec son motif et son auteur.
        """
        resultat = self.get_object()
        serializer = DecisionOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if resultat.semester.state == SemesterState.PUBLISHED:
            raise ValidationError(
                "لا يمكن تعديل القرار بعد النشر. أعد الفصل إلى حالة « مغلق » أولا."
            )

        ancienne = resultat.decision_final
        resultat.decision_final = serializer.validated_data["decision"]
        resultat.override_reason = serializer.validated_data["reason"]
        resultat.overridden_by = request.user
        resultat.save(
            update_fields=["decision_final", "override_reason", "overridden_by"]
        )

        audit.info(
            "Decision modifiee — etudiante=%s فصل=%s %s → %s motif=%s par=%s",
            resultat.enrollment.student.matricule,
            resultat.semester,
            ancienne,
            resultat.decision_final,
            resultat.override_reason,
            request.user.username,
        )
        return Response(SemesterResultSerializer(resultat).data)


class AnnualResultViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AnnualResultSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = [
        "year",
        "enrollment",
        "enrollment__section",
        "decision_final",
    ]
    queryset = AnnualResult.objects.none()
    ordering_fields = ["rank", "average"]

    def get_queryset(self) -> QuerySet[AnnualResult]:
        user = self.request.user
        base = AnnualResult.objects.select_related(
            "enrollment__student", "enrollment__section", "year"
        )
        if user.is_student:
            # Le resultat annuel n'a de sens qu'une fois les deux فصول publies.
            annees_publiees = Semester.objects.filter(
                state=SemesterState.PUBLISHED
            ).values_list("year_id", flat=True)
            return base.filter(
                enrollment__student__user=user, year_id__in=annees_publiees
            )
        return base.filter(enrollment__section__in=sections_visibles(user))


class MyResultsView(APIView):
    """
    Releve personnel de l'etudiante connectee : ses فصول publies et son
    resultat annuel, dans une seule reponse.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: None})
    def get(self, request: Request) -> Response:
        user = request.user
        if not user.is_student:
            # 403 plutot que 400 : ce n'est pas la requete qui est malformee,
            # c'est l'appelant qui n'a pas de releve personnel. L'administration
            # detient pourtant `resultats.personnels`, comme toutes les autres.
            raise PermissionDenied("هذه الواجهة مخصصة للطالبات.")

        semestriels = (
            SemesterResult.objects.filter(
                enrollment__student__user=user,
                semester__state=SemesterState.PUBLISHED,
            )
            .select_related("enrollment__section", "semester", "rule")
            .prefetch_related("subject_results__curriculum__subject")
            .order_by("semester__number", "session")
        )
        annuels = AnnualResult.objects.filter(
            enrollment__student__user=user
        ).select_related("year", "enrollment__section")

        return Response(
            {
                "semesters": SemesterResultSerializer(semestriels, many=True).data,
                "annual": AnnualResultSerializer(annuels, many=True).data,
            }
        )


class RecomputeView(APIView):
    """
    Relance manuelle du calcul.

    Le recalcul est normalement automatique a chaque enregistrement de notes ;
    cette route sert apres un changement de coefficient ou de reglement.
    """

    permission_classes = [PeutDeliberer]

    @extend_schema(request=RecomputeSerializer, responses={200: None})
    def post(self, request: Request) -> Response:
        serializer = RecomputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data

        if donnees.get("annual"):
            year = get_object_or_404(AcademicYear, is_active=True)
            sections = (
                [get_object_or_404(Section, pk=donnees["section"])]
                if donnees.get("section")
                else Section.objects.filter(is_active=True)
            )
            resultat = {
                s.name_ar: recompute_annual(year, s) for s in sections
            }
        else:
            if not donnees.get("semester"):
                raise ValidationError({"semester": "المعامل مطلوب."})
            semester = get_object_or_404(Semester, pk=donnees["semester"])
            session = donnees.get("session") or semester.current_session
            if donnees.get("section"):
                section = get_object_or_404(Section, pk=donnees["section"])
                resultat = {
                    section.name_ar: recompute_semester(semester, section, session)
                }
            else:
                resultat = recompute_semester_all_sections(semester, session)

        audit.info("Recalcul manuel par %s : %s", request.user.username, resultat)
        return Response({"recalcul": resultat})
