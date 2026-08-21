"""
Vues de la structure pedagogique.

Chaque `get_queryset` restreint ce que le role a le droit de voir. Un
enseignant qui forge l'identifiant d'une section qu'il n'enseigne pas obtient
un 404, pas la donnee.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    ExamSession,
    Section,
    Semester,
    SemesterState,
    Subject,
    TeachingAssignment,
)
from apps.academics.serializers import (
    AcademicYearSerializer,
    DuplicationAnneeSerializer,
    ReinscriptionSerializer,
    CurriculumSerializer,
    EnrollmentSerializer,
    SectionSerializer,
    SemesterSerializer,
    SubjectSerializer,
    TeachingAssignmentSerializer,
)
from apps.accounts.models import Student
from apps.common.permissions import (
    LectureOuAnnees,
    LectureOuEtudiantes,
    LectureOuStructure,
    PeutDeliberer,
    PeutGererAnnees,
    PeutGererEtudiantes,
    PeutGererStructure,
)
from apps.results.serializers import SeuilSectionSerializer
from apps.results.services import (
    ThresholdOutOfRange,
    default_rule_for,
    recompute_semester,
    recompute_semester_all_sections,
    resolve_rule,
    set_section_threshold,
)

audit = logging.getLogger("asleyn.audit")


def sections_visibles(user) -> QuerySet[Section]:
    """
    Sections auxquelles un utilisateur a acces.

    Admin : toutes. Enseignant : celles ou il a une affectation active.
    Etudiante : la sienne uniquement.
    """
    if user.is_staff_role:
        return Section.objects.all()
    if user.is_teacher:
        return Section.objects.filter(
            curricula__assignments__teacher__user=user,
            curricula__assignments__is_active=True,
        ).distinct()
    return Section.objects.filter(
        enrollments__student__user=user, enrollments__is_active=True
    ).distinct()


class AcademicYearViewSet(viewsets.ModelViewSet):
    serializer_class = AcademicYearSerializer
    permission_classes = [LectureOuAnnees]
    queryset = AcademicYear.objects.all()
    filterset_fields = ["is_active"]

    @extend_schema(
        request=DuplicationAnneeSerializer, responses={201: AcademicYearSerializer}
    )
    @action(detail=True, methods=["post"], permission_classes=[PeutGererAnnees])
    def dupliquer(self, request: Request, pk: str | None = None) -> Response:
        """
        Ouvre l'annee suivante en recopiant la structure de celle-ci.

        Sont recopies : les فصول (numeros, poids), les programmes et leurs
        coefficients, et le reglement de notation. Ne sont **pas** recopies :
        les inscriptions, les notes et les resultats. La reinscription des
        etudiantes est un acte distinct et explicite.
        """
        source: AcademicYear = self.get_object()
        serializer = DuplicationAnneeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data

        with transaction.atomic():
            if donnees["activer"]:
                AcademicYear.objects.filter(is_active=True).update(is_active=False)

            cible = AcademicYear.objects.create(
                label=donnees["label"],
                start_date=donnees["start_date"],
                end_date=donnees["end_date"],
                is_active=donnees["activer"],
            )
            default_rule_for(cible)

            fusul = 0
            programmes = 0
            for ancien in source.semesters.all().order_by("number"):
                nouveau = Semester.objects.create(
                    year=cible,
                    number=ancien.number,
                    # Les dates sont decalees d'un an : l'administration les
                    # ajustera, mais elles ne sont jamais vides.
                    start_date=ancien.start_date.replace(
                        year=ancien.start_date.year + 1
                    ),
                    end_date=ancien.end_date.replace(year=ancien.end_date.year + 1),
                    state=SemesterState.DRAFT,
                    weight=ancien.weight,
                )
                fusul += 1
                for programme in ancien.curricula.all():
                    Curriculum.objects.create(
                        section=programme.section,
                        semester=nouveau,
                        subject=programme.subject,
                        coefficient=programme.coefficient,
                        display_order=programme.display_order,
                        is_active=programme.is_active,
                    )
                    programmes += 1

        audit.info(
            "Annee %s ouverte depuis %s par %s : %d فصول, %d programmes",
            cible.label,
            source.label,
            request.user.username,
            fusul,
            programmes,
        )
        return Response(
            {
                **AcademicYearSerializer(cible).data,
                "fusul_crees": fusul,
                "programmes_copies": programmes,
            },
            status=status.HTTP_201_CREATED,
        )


class SemesterViewSet(viewsets.ModelViewSet):
    serializer_class = SemesterSerializer
    permission_classes = [LectureOuStructure]
    queryset = Semester.objects.select_related("year")
    filterset_fields = ["year", "number", "state"]

    # Transitions autorisees. Toute autre combinaison est refusee : l'etat
    # d'un فصل ne recule pas par accident.
    TRANSITIONS = {
        SemesterState.DRAFT: {SemesterState.OPEN},
        SemesterState.OPEN: {SemesterState.CLOSED},
        SemesterState.CLOSED: {SemesterState.OPEN, SemesterState.PUBLISHED},
        SemesterState.PUBLISHED: {SemesterState.CLOSED},
    }

    def _transition(self, request: Request, cible: SemesterState) -> Response:
        semester = self.get_object()
        if cible not in self.TRANSITIONS[semester.state]:
            raise ValidationError(
                {
                    "state": (
                        f"انتقال غير مسموح: {semester.get_state_display()} → "
                        f"{SemesterState(cible).label}"
                    )
                }
            )

        semester.state = cible
        if cible == SemesterState.PUBLISHED:
            semester.published_at = timezone.now()
        semester.save(update_fields=["state", "published_at"])

        audit.info(
            "Changement d'etat du فصل %s → %s par %s",
            semester,
            cible,
            request.user.username,
        )

        # A la cloture, on fige un calcul a jour avant deliberation — pour la
        # session que le فصل a ouverte, pas pour l'autre.
        recalcul = {}
        if cible == SemesterState.CLOSED:
            recalcul = recompute_semester_all_sections(
                semester, semester.current_session
            )

        return Response(
            {**SemesterSerializer(semester).data, "recalcul": recalcul},
            status=status.HTTP_200_OK,
        )

    @extend_schema(request=None, responses={200: SemesterSerializer})
    @action(detail=True, methods=["post"], permission_classes=[PeutDeliberer])
    def open(self, request: Request, pk: str | None = None) -> Response:
        """Ouvre la saisie des notes."""
        return self._transition(request, SemesterState.OPEN)

    @extend_schema(request=None, responses={200: SemesterSerializer})
    @action(detail=True, methods=["post"], permission_classes=[PeutDeliberer])
    def close(self, request: Request, pk: str | None = None) -> Response:
        """Ferme la saisie et recalcule toutes les sections."""
        return self._transition(request, SemesterState.CLOSED)

    @extend_schema(request=None, responses={200: SemesterSerializer})
    @action(detail=True, methods=["post"], permission_classes=[PeutDeliberer])
    def publish(self, request: Request, pk: str | None = None) -> Response:
        """Publie les resultats : ils deviennent visibles des etudiantes."""
        return self._transition(request, SemesterState.PUBLISHED)

    @extend_schema(request=None, responses={200: SemesterSerializer})
    @action(
        detail=True,
        methods=["post"],
        url_path="open-resit",
        permission_classes=[PeutDeliberer],
    )
    def open_resit(self, request: Request, pk: str | None = None) -> Response:
        """
        Ouvre la session de rattrapage.

        Le فصل repasse en saisie, mais dans la seconde session : les notes de
        la session normale restent intactes, et seules les etudiantes
        convoquees apparaissent dans les grilles.

        Exige que la session normale ait ete publiee : c'est la publication
        qui informe les etudiantes de leur convocation.
        """
        semester = self.get_object()
        if semester.current_session == ExamSession.RESIT:
            raise ValidationError(
                {"session": "الدورة الاستدراكية مفتوحة أصلا."}
            )
        if semester.state != SemesterState.PUBLISHED:
            raise ValidationError(
                {
                    "state": (
                        "يجب نشر نتائج الدورة العادية قبل فتح الدورة "
                        "الاستدراكية."
                    )
                }
            )

        semester.current_session = ExamSession.RESIT
        semester.state = SemesterState.OPEN
        semester.save(update_fields=["current_session", "state"])

        audit.info(
            "Session de rattrapage ouverte — %s par %s",
            semester,
            request.user.username,
        )
        return Response(SemesterSerializer(semester).data)

    @extend_schema(request=SeuilSectionSerializer, responses={200: None})
    @action(detail=True, methods=["post"], permission_classes=[PeutDeliberer])
    def seuil(self, request: Request, pk: str | None = None) -> Response:
        """
        Fixe en deliberation les seuils d'un قسم pour ce فصل — barre de
        reussite et, facultativement, plancher de compensation — puis
        recalcule la section avec eux.
        """
        semester = self.get_object()
        serializer = SeuilSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        section = get_object_or_404(
            Section, pk=serializer.validated_data["section"]
        )
        if semester.state == SemesterState.PUBLISHED:
            raise ValidationError(
                "لا يمكن تغيير العتبة بعد النشر. أعد الفصل إلى حالة « مغلق » أولا."
            )

        try:
            rule = set_section_threshold(
                semester=semester,
                section=section,
                pass_threshold=serializer.validated_data["pass_threshold"],
                compensation_floor=serializer.validated_data.get(
                    "compensation_floor"
                ),
                user=request.user,
                note=serializer.validated_data.get("note", ""),
            )
        except ThresholdOutOfRange as erreur:
            raise ValidationError({"pass_threshold": str(erreur)}) from erreur

        traitees = recompute_semester(semester, section, semester.current_session)

        return Response(
            {
                "section": section.name_ar,
                "pass_threshold": str(rule.pass_threshold),
                # Renvoye meme quand la commission ne l'a pas fixe : il a pu
                # etre borne par la barre, et le front doit le signaler.
                "compensation_floor": str(rule.compensation_floor),
                "version": rule.version,
                "etudiantes_recalculees": traitees,
            }
        )

    @extend_schema(responses={200: None})
    @action(detail=True, methods=["get"], url_path="seuils")
    def seuils(self, request: Request, pk: str | None = None) -> Response:
        """Barre de reussite effectivement appliquee a chaque قسم."""
        semester = self.get_object()
        lignes = []
        for section in Section.objects.filter(
            curricula__semester=semester, curricula__is_active=True
        ).distinct():
            rule = resolve_rule(semester.year, section, semester)
            lignes.append(
                {
                    "section": section.id,
                    "section_name": section.name_ar,
                    "pass_threshold": str(rule.pass_threshold),
                    "compensation_floor": str(rule.compensation_floor),
                    "version": rule.version,
                    "propre_au_fasl": rule.semester_id == semester.id,
                    "note": rule.note,
                }
            )
        return Response(lignes)


class SectionViewSet(viewsets.ModelViewSet):
    serializer_class = SectionSerializer
    permission_classes = [LectureOuStructure]
    filterset_fields = ["is_active"]
    # Renseigne pour la generation du schema ; le filtrage reel est dans get_queryset.
    queryset = Section.objects.none()

    def get_queryset(self) -> QuerySet[Section]:
        return sections_visibles(self.request.user).annotate(
            student_count=Count(
                "enrollments", filter=Q(enrollments__is_active=True), distinct=True
            )
        )


class SubjectViewSet(viewsets.ModelViewSet):
    """Catalogue des matieres : referentiel commun, lisible par tous."""

    serializer_class = SubjectSerializer
    permission_classes = [LectureOuStructure]
    queryset = Subject.objects.all()
    filterset_fields = ["is_active"]


class CurriculumViewSet(viewsets.ModelViewSet):
    """
    Programme d'un فصل : la table qui porte les coefficients.

    Modifier un coefficient change les moyennes : l'operation est reservee a
    l'administration, et refusee des lors que le فصل est publie.
    """

    serializer_class = CurriculumSerializer
    permission_classes = [LectureOuStructure]
    filterset_fields = ["section", "semester", "subject", "is_active"]
    queryset = Curriculum.objects.none()

    def get_queryset(self) -> QuerySet[Curriculum]:
        return (
            Curriculum.objects.filter(
                section__in=sections_visibles(self.request.user)
            )
            .select_related("section", "subject", "semester")
        )

    def _refuser_si_publie(self, semester: Semester) -> None:
        if semester.state == SemesterState.PUBLISHED:
            raise ValidationError(
                "لا يمكن تعديل البرنامج بعد نشر نتائج الفصل."
            )

    def perform_create(self, serializer) -> None:
        self._refuser_si_publie(serializer.validated_data["semester"])
        instance = serializer.save()
        audit.info(
            "Programme cree : %s par %s", instance, self.request.user.username
        )

    def perform_update(self, serializer) -> None:
        self._refuser_si_publie(serializer.instance.semester)
        ancien = serializer.instance.coefficient
        instance = serializer.save()
        if ancien != instance.coefficient:
            audit.info(
                "Coefficient modifie : %s %s → %s par %s",
                instance,
                ancien,
                instance.coefficient,
                self.request.user.username,
            )

    def perform_destroy(self, instance: Curriculum) -> None:
        self._refuser_si_publie(instance.semester)
        if instance.grades.exists():
            raise ValidationError(
                "لا يمكن حذف مادة تحتوي على نقاط مسجلة. عطّلها بدل حذفها."
            )
        instance.delete()


class EnrollmentViewSet(viewsets.ModelViewSet):
    serializer_class = EnrollmentSerializer
    permission_classes = [LectureOuEtudiantes]
    filterset_fields = ["section", "year", "is_active"]
    search_fields = ["student__matricule", "student__full_name_ar"]
    ordering_fields = ["student__matricule", "student__full_name_ar"]
    ordering = ["student__matricule"]
    queryset = Enrollment.objects.none()

    def get_queryset(self) -> QuerySet[Enrollment]:
        user = self.request.user
        base = Enrollment.objects.select_related("student", "section", "year")
        if user.is_student:
            return base.filter(student__user=user)
        return base.filter(section__in=sections_visibles(user))

    @extend_schema(request=ReinscriptionSerializer, responses={200: None})
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[PeutGererEtudiantes],
    )
    def reinscrire(self, request: Request) -> Response:
        """
        Reinscrit un lot d'etudiantes dans une annee et une section.

        Idempotent : une etudiante deja inscrite dans l'annee cible est
        signalee, pas dupliquee — la base n'autorise de toute facon qu'une
        seule section par etudiante et par annee.
        """
        serializer = ReinscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data

        year = get_object_or_404(AcademicYear, pk=donnees["year"])
        section = get_object_or_404(Section, pk=donnees["section"])

        demandees = set(donnees["students"])
        existantes = dict(
            Enrollment.objects.filter(
                student_id__in=demandees, year=year
            ).values_list("student_id", "section__name_ar")
        )
        connues = set(
            Student.objects.filter(id__in=demandees).values_list("id", flat=True)
        )
        inconnues = sorted(demandees - connues)

        a_creer = [
            Enrollment(student_id=identifiant, section=section, year=year)
            for identifiant in sorted(connues - set(existantes))
        ]
        with transaction.atomic():
            Enrollment.objects.bulk_create(a_creer)

        audit.info(
            "Reinscription %s / %s : %d creees, %d deja inscrites, par %s",
            section.name_ar,
            year.label,
            len(a_creer),
            len(existantes),
            request.user.username,
        )
        return Response(
            {
                "annee": year.label,
                "section": section.name_ar,
                "inscrites": len(a_creer),
                "deja_inscrites": [
                    {"student": identifiant, "section": nom}
                    for identifiant, nom in existantes.items()
                ],
                "introuvables": inconnues,
            }
        )


class TeachingAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = TeachingAssignmentSerializer
    permission_classes = [PeutGererStructure]
    queryset = TeachingAssignment.objects.select_related(
        "teacher", "curriculum__subject", "curriculum__section"
    )
    filterset_fields = ["teacher", "curriculum", "is_active"]
