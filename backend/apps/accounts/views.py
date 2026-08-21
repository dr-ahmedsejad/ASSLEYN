"""
Authentification et profils.

Modele retenu : session Django en cookie httpOnly, pose par le BFF Next.js.
Aucun jeton n'est jamais expose au JavaScript du navigateur, ce qui retire
d'emblee tout interet a un vol de jeton par XSS.
"""

from __future__ import annotations

import logging

from django.contrib.auth import login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Student, Teacher
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    StudentSerializer,
    TeacherSerializer,
    UserSerializer,
)
from apps.common.permissions import PeutGererComptes, PeutGererEtudiantes

audit = logging.getLogger("asleyn.audit")


def _client_ip(request: Request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "?")


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Pose le cookie CSRF avant toute ecriture."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    """Ouverture de session. Limitee a 10 tentatives par heure et par IP."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        login(request, user)
        # Nouvelle session a chaque connexion : protege de la fixation de session.
        request.session.cycle_key()

        audit.info(
            "Connexion reussie — utilisateur=%s role=%s ip=%s",
            user.username,
            user.role,
            _client_ip(request),
        )
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        audit.info(
            "Deconnexion — utilisateur=%s ip=%s",
            request.user.username,
            _client_ip(request),
        )
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """
    Changement de mot de passe.

    Accessible meme quand `must_change_password` est vrai : c'est precisement
    la route qui permet d'en sortir.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Conserve la session active malgre le changement de hash.
        update_session_auth_hash(request, user)
        audit.info("Mot de passe change — utilisateur=%s", user.username)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentViewSet(viewsets.ModelViewSet):
    """Dossiers des etudiantes. Administration uniquement."""

    serializer_class = StudentSerializer
    permission_classes = [PeutGererEtudiantes]
    queryset = Student.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["matricule", "full_name_ar"]
    ordering_fields = ["matricule", "full_name_ar"]


class TeacherViewSet(viewsets.ModelViewSet):
    serializer_class = TeacherSerializer
    permission_classes = [PeutGererComptes]
    queryset = Teacher.objects.select_related("user")
    filterset_fields = ["is_active"]
