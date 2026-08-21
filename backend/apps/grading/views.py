"""
Saisie des notes.

L'ecran critique du systeme est la grille de l'enseignant : une colonne par
matiere, une ligne par etudiante. Deux routes le servent — une lecture qui
renvoie la grille prete a afficher, une ecriture en lot qui enregistre la
colonne entiere en une transaction.

Trois verrous, verifies a chaque appel et pas seulement a l'affichage :
le فصل doit etre ouvert, l'enseignant doit etre affecte a cette matiere, et
chaque note doit rester dans le bareme du reglement.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Curriculum, Enrollment, ExamSession
from apps.academics.views import sections_visibles
from apps.common.permissions import (
    PeutConsulterJournal,
    PeutConsulterNotes,
    PeutDeliberer,
    PeutSaisirNotes,
    PeutVoirLaSaisie,
)
from apps.grading.models import Grade, GradeHistory, GradeStatus, GradingRule
from apps.grading.serializers import (
    BulkGradeSerializer,
    GradeHistorySerializer,
    GradeSerializer,
    GradeRowSerializer,
    GradingRuleSerializer,
)
from apps.results.services import (
    recompute_semester,
    resit_candidates,
    resolve_rule,
)

audit = logging.getLogger("asleyn.audit")


def curriculum_autorise(user, curriculum_id: int, pour_ecriture: bool) -> Curriculum:
    """
    Verifie qu'un utilisateur peut lire — ou ecrire — les notes d'une matiere.

    Retourne le programme, ou leve une erreur explicite. L'administration a
    tous les droits de lecture et d'ecriture ; un enseignant est limite a ses
    affectations actives.
    """
    curriculum = get_object_or_404(
        Curriculum.objects.select_related("section", "subject", "semester__year"),
        pk=curriculum_id,
    )

    if not user.is_staff_role:
        if not user.is_teacher:
            raise PermissionDenied("هذه العملية مخصصة للإدارة والأساتذة.")
        affecte = curriculum.assignments.filter(
            teacher__user=user, is_active=True
        ).exists()
        if not affecte:
            raise PermissionDenied("لست مسندا لهذه المادة.")

    if pour_ecriture and not curriculum.semester.accepts_grade_entry:
        raise ValidationError(
            {
                "semester": (
                    "الفصل غير مفتوح لإدخال النقاط "
                    f"(الحالة الحالية: {curriculum.semester.get_state_display()})."
                )
            }
        )
    return curriculum


class GradeSheetView(APIView):
    """Grille de saisie d'une matiere : toutes les etudiantes de la section."""

    permission_classes = [PeutVoirLaSaisie]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "curriculum",
                int,
                required=True,
                description="Identifiant du programme (matiere × فصل × section).",
            )
        ],
        responses={200: GradeRowSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        curriculum_id = request.query_params.get("curriculum")
        if not curriculum_id:
            raise ValidationError({"curriculum": "المعامل مطلوب."})

        curriculum = curriculum_autorise(
            request.user, int(curriculum_id), pour_ecriture=False
        )
        semester = curriculum.semester
        session = request.query_params.get("session") or semester.current_session
        if session not in ExamSession.values:
            raise ValidationError({"session": "دورة غير معروفة."})

        enrollments = (
            Enrollment.objects.filter(
                section=curriculum.section,
                year=semester.year,
                is_active=True,
            )
            .select_related("student")
            .order_by("student__matricule")
        )

        # En rattrapage, seules les etudiantes convoquees figurent dans la
        # grille : celles declarees غير مستوفي dans cette matiere a l'issue de
        # la session normale.
        convoquees: set[int] | None = None
        if session == ExamSession.RESIT:
            convoquees = resit_candidates(semester, curriculum)
            enrollments = [e for e in enrollments if e.id in convoquees]

        notes = {
            (g.enrollment_id, g.session): g
            for g in Grade.objects.filter(
                curriculum=curriculum, enrollment__in=enrollments
            )
        }

        lignes = []
        for enrollment in enrollments:
            note = notes.get((enrollment.id, session))
            normale = notes.get((enrollment.id, ExamSession.NORMAL))
            lignes.append(
                {
                    "enrollment": enrollment.id,
                    "matricule": enrollment.student.matricule,
                    "full_name_ar": enrollment.student.full_name_ar,
                    # Chaine et non nombre : c'est la convention de DRF pour les
                    # decimaux, et le front attend le meme type partout.
                    "value": None if note is None or note.value is None else str(note.value),
                    "status": note.status if note else GradeStatus.MISSING,
                    # Rappel de la note obtenue en session normale, pour que
                    # l'enseignant voie ce que le rattrapage doit ameliorer.
                    "normal_value": (
                        None
                        if session == ExamSession.NORMAL
                        or normale is None
                        or normale.value is None
                        else str(normale.value)
                    ),
                    "updated_at": note.updated_at if note else None,
                }
            )

        rule = resolve_rule(semester.year, curriculum.section, semester)
        saisies = sum(1 for r in lignes if r["status"] != GradeStatus.MISSING)
        return Response(
            {
                "curriculum": {
                    "id": curriculum.id,
                    "section_name": curriculum.section.name_ar,
                    "subject_name": curriculum.subject.name_ar,
                    "coefficient": str(curriculum.coefficient),
                    "semester_number": semester.number,
                    "semester_state": semester.state,
                    "editable": (
                        semester.accepts_grade_entry
                        and session == semester.current_session
                    ),
                },
                "session": session,
                "session_display": dict(ExamSession.choices)[session],
                "current_session": semester.current_session,
                "max_grade": str(rule.max_grade),
                "completion": {"saisies": saisies, "total": len(lignes)},
                "rows": lignes,
            }
        )


class BulkGradeView(APIView):
    """
    Enregistrement en lot d'une colonne de notes.

    Tout ou rien : une seule ligne invalide annule l'ensemble. Chaque
    changement est journalise dans `GradeHistory`, puis la section est
    recalculee.
    """

    permission_classes = [PeutSaisirNotes]

    @extend_schema(request=BulkGradeSerializer, responses={200: None})
    def post(self, request: Request) -> Response:
        curriculum_id = request.data.get("curriculum")
        if curriculum_id is None:
            raise ValidationError({"curriculum": "المعامل مطلوب."})

        curriculum = curriculum_autorise(
            request.user, int(curriculum_id), pour_ecriture=True
        )
        semester = curriculum.semester
        # La session ecrite est toujours celle que le فصل a ouverte : le client
        # ne choisit pas dans quelle session il ecrit.
        session = semester.current_session
        rule: GradingRule = resolve_rule(semester.year, curriculum.section, semester)

        serializer = BulkGradeSerializer(
            data=request.data, context={"max_grade": rule.max_grade}
        )
        serializer.is_valid(raise_exception=True)
        lignes = serializer.validated_data["grades"]

        # Les inscriptions doivent appartenir a la section de la matiere :
        # sinon on ecrirait la note d'une etudiante d'une autre section.
        autorisees = set(
            Enrollment.objects.filter(
                section=curriculum.section,
                year=semester.year,
                is_active=True,
            ).values_list("id", flat=True)
        )
        # En rattrapage, on restreint encore : seules les convoquees de cette
        # matiere peuvent recevoir une note.
        if session == ExamSession.RESIT:
            autorisees &= resit_candidates(semester, curriculum)

        intrus = [
            r["enrollment"] for r in lignes if r["enrollment"] not in autorisees
        ]
        if intrus:
            message = (
                "طالبات غير معنيات بالدورة الاستدراكية في هذه المادة"
                if session == ExamSession.RESIT
                else "تسجيلات لا تنتمي إلى هذا القسم"
            )
            raise ValidationError({"grades": f"{message}: {intrus}"})

        with transaction.atomic():
            modifiees = 0
            for ligne in lignes:
                note, cree = Grade.objects.select_for_update().get_or_create(
                    enrollment_id=ligne["enrollment"],
                    curriculum=curriculum,
                    session=session,
                    defaults={
                        "value": ligne["value"],
                        "status": ligne["status"],
                        "entered_by": request.user,
                    },
                )
                ancien_valeur, ancien_statut = note.value, note.status

                if not cree:
                    inchange = (
                        note.value == ligne["value"] and note.status == ligne["status"]
                    )
                    if inchange:
                        continue
                    note.value = ligne["value"]
                    note.status = ligne["status"]
                    note.entered_by = request.user
                    note.save(
                        update_fields=["value", "status", "entered_by", "updated_at"]
                    )

                GradeHistory.objects.create(
                    grade=note,
                    old_value=None if cree else ancien_valeur,
                    new_value=note.value,
                    old_status="" if cree else ancien_statut,
                    new_status=note.status,
                    session=session,
                    reason=ligne.get("reason", ""),
                    changed_by=request.user,
                )
                modifiees += 1

            traitees = recompute_semester(semester, curriculum.section, session)

        audit.info(
            "Notes enregistrees — matiere=%s section=%s session=%s modifiees=%d par=%s",
            curriculum.subject.name_ar,
            curriculum.section.name_ar,
            session,
            modifiees,
            request.user.username,
        )
        return Response(
            {
                "modifiees": modifiees,
                "recues": len(lignes),
                "session": session,
                "etudiantes_recalculees": traitees,
            },
            status=status.HTTP_200_OK,
        )


class GradeViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des notes, filtree par ce que le role a le droit de voir."""

    serializer_class = GradeSerializer
    permission_classes = [PeutConsulterNotes]
    filterset_fields = ["curriculum", "enrollment", "status", "session"]
    queryset = Grade.objects.none()

    def get_queryset(self) -> QuerySet[Grade]:
        user = self.request.user
        base = Grade.objects.select_related(
            "enrollment__student", "curriculum__subject", "curriculum__section"
        )
        if user.is_staff_role:
            return base
        # Un enseignant ne voit que les notes des matieres qu'il enseigne.
        return base.filter(
            curriculum__assignments__teacher__user=user,
            curriculum__assignments__is_active=True,
        ).distinct()


class GradeHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Journal des modifications de notes."""

    serializer_class = GradeHistorySerializer
    permission_classes = [PeutConsulterJournal]
    filterset_fields = [
        "grade",
        "grade__curriculum__section",
        "grade__curriculum__semester",
        "changed_by",
    ]
    search_fields = [
        "grade__enrollment__student__matricule",
        "grade__enrollment__student__full_name_ar",
    ]
    ordering_fields = ["changed_at"]
    queryset = GradeHistory.objects.none()

    def get_queryset(self) -> QuerySet[GradeHistory]:
        user = self.request.user
        base = GradeHistory.objects.select_related(
            "changed_by",
            "grade__enrollment__student",
            "grade__curriculum__subject",
            "grade__curriculum__section",
        )
        if user.is_staff_role:
            return base
        return base.filter(
            grade__curriculum__section__in=sections_visibles(user)
        ).distinct()


class GradingRuleViewSet(viewsets.ModelViewSet):
    """
    Reglement de notation.

    Reserve a l'administration : ces valeurs determinent qui reussit.
    """

    serializer_class = GradingRuleSerializer
    permission_classes = [PeutDeliberer]
    queryset = GradingRule.objects.select_related("year", "section")
    filterset_fields = ["year", "section", "is_active"]

    def perform_create(self, serializer) -> None:
        instance = serializer.save()
        audit.info(
            "Reglement cree : %s par %s", instance, self.request.user.username
        )

    def perform_update(self, serializer) -> None:
        instance = serializer.save()
        audit.info(
            "Reglement modifie : %s par %s", instance, self.request.user.username
        )
