"""
Avancement de la saisie.

Un assistant qui saisit les notes de tout un فصل a besoin de savoir, d'un coup
d'oeil, ou il en est : quelles matieres sont terminees, lesquelles sont
entamees, lesquelles n'ont pas commence. Sans cela il ouvre les grilles une a
une pour le decouvrir.

Cette vue repond en trois requetes, quel que soit le nombre de matieres — pas
une par grille.
"""

from __future__ import annotations

from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import Curriculum, Enrollment, ExamSession, Semester
from apps.common.permissions import PeutVoirLaSaisie
from apps.grading.models import Grade, GradeStatus
from apps.results.models import SubjectResult


def _convoquees_par_matiere(semester: Semester) -> dict[int, int]:
    """
    Nombre d'etudiantes convoquees au rattrapage, par matiere.

    Meme regle que `resit_candidates`, mais en une seule requete pour tout le
    فصل : la vue d'avancement liste des dizaines de matieres.
    """
    lignes = (
        SubjectResult.objects.filter(
            semester_result__semester=semester,
            semester_result__session=ExamSession.NORMAL,
            semester_result__decision_final="RESIT",
            decision="NOT_SATISFIED",
        )
        .values("curriculum_id")
        .annotate(total=Count("semester_result__enrollment_id", distinct=True))
    )
    return {ligne["curriculum_id"]: ligne["total"] for ligne in lignes}


class AvancementSaisieView(APIView):
    """
    Etat de la saisie d'un فصل, matiere par matiere et قسم par قسم.

    Un enseignant n'y voit que ses matieres affectees ; le personnel de
    l'institut, toutes celles du فصل.
    """

    permission_classes = [PeutVoirLaSaisie]

    @extend_schema(
        parameters=[
            OpenApiParameter("semester", int, required=True),
            OpenApiParameter("session", str, required=False),
        ],
        responses={200: None},
    )
    def get(self, request: Request) -> Response:
        identifiant = request.query_params.get("semester")
        if not identifiant:
            raise ValidationError({"semester": "المعامل مطلوب."})

        try:
            semester = Semester.objects.select_related("year").get(pk=identifiant)
        except (Semester.DoesNotExist, ValueError) as erreur:
            raise ValidationError({"semester": "فصل غير معروف."}) from erreur

        session = request.query_params.get("session") or semester.current_session
        if session not in ExamSession.values:
            raise ValidationError({"session": "دورة غير معروفة."})

        curricula = (
            Curriculum.objects.filter(semester=semester, is_active=True)
            .select_related("section", "subject")
            .order_by("section__display_order", "display_order", "subject__name_ar")
        )

        user = request.user
        if not user.is_staff_role:
            # Un enseignant ne voit que ce qu'il enseigne.
            curricula = curricula.filter(
                assignments__teacher__user=user, assignments__is_active=True
            ).distinct()

        curricula = list(curricula)
        if not curricula:
            return Response(
                {
                    "semester": _resume_fasl(semester, session),
                    "total": {"attendues": 0, "saisies": 0},
                    "sections": [],
                }
            )

        effectifs = {
            ligne["section_id"]: ligne["total"]
            for ligne in Enrollment.objects.filter(
                year=semester.year, is_active=True
            )
            .values("section_id")
            .annotate(total=Count("id"))
        }

        # Une note « renseignee » est une note dont le statut a ete arrete —
        # y compris une absence. Seul `MISSING` compte comme non saisie.
        saisies = {
            ligne["curriculum_id"]: ligne["total"]
            for ligne in Grade.objects.filter(
                curriculum__in=curricula, session=session
            )
            .exclude(status=GradeStatus.MISSING)
            .values("curriculum_id")
            .annotate(total=Count("id"))
        }

        convoquees = (
            _convoquees_par_matiere(semester)
            if session == ExamSession.RESIT
            else {}
        )

        par_section: dict[int, dict] = {}
        total_attendues = total_saisies = 0

        for curriculum in curricula:
            attendues = (
                convoquees.get(curriculum.id, 0)
                if session == ExamSession.RESIT
                else effectifs.get(curriculum.section_id, 0)
            )
            faites = min(saisies.get(curriculum.id, 0), attendues)
            total_attendues += attendues
            total_saisies += faites

            bloc = par_section.setdefault(
                curriculum.section_id,
                {
                    "id": curriculum.section_id,
                    "name_ar": curriculum.section.name_ar,
                    "effectif": effectifs.get(curriculum.section_id, 0),
                    "attendues": 0,
                    "saisies": 0,
                    "matieres": [],
                },
            )
            bloc["attendues"] += attendues
            bloc["saisies"] += faites
            bloc["matieres"].append(
                {
                    "curriculum": curriculum.id,
                    "subject_name": curriculum.subject.name_ar,
                    "subject_code": curriculum.subject.code,
                    "coefficient": str(curriculum.coefficient),
                    "attendues": attendues,
                    "saisies": faites,
                    "statut": _statut(faites, attendues),
                }
            )

        return Response(
            {
                "semester": _resume_fasl(semester, session),
                "total": {"attendues": total_attendues, "saisies": total_saisies},
                "sections": list(par_section.values()),
            }
        )


def _statut(saisies: int, attendues: int) -> str:
    if attendues == 0:
        return "SANS_OBJET"
    if saisies == 0:
        return "NON_COMMENCEE"
    if saisies >= attendues:
        return "COMPLETE"
    return "PARTIELLE"


def _resume_fasl(semester: Semester, session: str) -> dict:
    return {
        "id": semester.id,
        "number": semester.number,
        "year_label": semester.year.label,
        "state": semester.state,
        "state_display": semester.get_state_display(),
        "session": session,
        "session_display": dict(ExamSession.choices)[session],
        "current_session": semester.current_session,
        "editable": semester.accepts_grade_entry
        and session == semester.current_session,
    }
