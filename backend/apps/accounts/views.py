"""
Authentification et profils.

Modele retenu : session Django en cookie httpOnly, pose par le BFF Next.js.
Aucun jeton n'est jamais expose au JavaScript du navigateur, ce qui retire
d'emblee tout interet a un vol de jeton par XSS.
"""

from __future__ import annotations

import logging

from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
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

from apps.accounts import verrouillage
from apps.accounts.models import LoginOutcome, Student, Teacher, User
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


#: Message unique pour tout echec d'identification. Ne jamais laisser deviner
#: si un compte existe : c'est la premiere information que cherche celui qui
#: essaie des identifiants au hasard.
MESSAGE_IDENTIFIANTS = "اسم المستخدم أو كلمة السر غير صحيحة."


def _charge_verrou(etat: verrouillage.EtatVerrou) -> dict:
    """Corps de reponse d'un compte bloque, minuteur compris."""
    minutes = max(round(etat.secondes_restantes / 60), 1)
    return {
        "detail": (
            f"تم إقفال الحساب مؤقتا بعد عدة محاولات خاطئة. "
            f"أعد المحاولة بعد {minutes} دقيقة."
        ),
        "verrouille": True,
        "secondes_restantes": etat.secondes_restantes,
        "niveau": etat.niveau,
    }


class LoginView(APIView):
    """
    Ouverture de session.

    Deux protections se superposent. Le throttle limite le debit par adresse
    IP, ce qui contient un balayage automatise. Le verrouillage, lui, porte
    sur le compte vise et **s'aggrave** a chaque serie d'echecs : 5 minutes,
    puis 15, puis 30. L'un ralentit la machine, l'autre ferme la porte.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        ip = _client_ip(request)
        agent = request.META.get("HTTP_USER_AGENT", "")

        # Le blocage se verifie AVANT le mot de passe. L'ordre inverse
        # laisserait un compte bloque servir d'oracle : pendant l'interdiction,
        # « mot de passe correct » ne doit pas etre une reponse possible.
        etat = verrouillage.etat(username)
        if etat.verrouille:
            verrouillage.journaliser(
                username,
                LoginOutcome.LOCKED,
                # Le compte est deja rattache au blocage : le journal affiche
                # le meme nom pour toutes les lignes d'un meme incident.
                user=etat.verrou.user if etat.verrou else None,
                ip=ip,
                user_agent=agent,
            )
            audit.warning(
                "Tentative sur un compte bloque — utilisateur=%s ip=%s", username, ip
            )
            return Response(_charge_verrou(etat), status=status.HTTP_423_LOCKED)

        user = authenticate(request=request, username=username, password=password)
        if user is None:
            # `authenticate` renvoie None dans les trois cas. Les distinguer
            # sert le journal, jamais la reponse.
            compte = User.objects.filter(username=username).first()
            if compte is None:
                issue = LoginOutcome.UNKNOWN_USER
            elif not compte.is_active:
                issue = LoginOutcome.INACTIVE
            else:
                issue = LoginOutcome.BAD_PASSWORD

            etat = verrouillage.enregistrer_echec(
                username, issue, user=compte, ip=ip, user_agent=agent
            )
            audit.warning(
                "Echec de connexion — utilisateur=%s issue=%s ip=%s",
                username,
                issue,
                ip,
            )
            if etat.verrouille:
                return Response(_charge_verrou(etat), status=status.HTTP_423_LOCKED)
            return Response(
                {
                    "detail": MESSAGE_IDENTIFIANTS,
                    "tentatives_restantes": etat.tentatives_restantes,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        # Nouvelle session a chaque connexion : protege de la fixation de session.
        request.session.cycle_key()
        verrouillage.enregistrer_succes(user, ip=ip, user_agent=agent)

        audit.info(
            "Connexion reussie — utilisateur=%s role=%s ip=%s",
            user.username,
            user.role,
            ip,
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
