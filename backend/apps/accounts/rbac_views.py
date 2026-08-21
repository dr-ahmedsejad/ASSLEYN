"""
Attribution des permissions aux roles.

Le catalogue est en lecture seule — chaque code garde un endpoint reel, on ne
peut pas en inventer un depuis l'interface. Ce qui se modifie ici, c'est la
matrice : quel role dispose de quelle capacite.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, RolePermission, User, UserPermission
from apps.accounts.rbac import CATEGORIES, Permission, est_verrouillee
from apps.common.permissions import PeutGererComptes

audit = logging.getLogger("asleyn.audit")


class AttributionSerializer(serializers.Serializer):
    """Une case de la matrice des droits."""

    role = serializers.ChoiceField(choices=Role.choices)
    permission = serializers.ChoiceField(choices=Permission.choices)
    accordee = serializers.BooleanField()


class MatriceSerializer(serializers.Serializer):
    attributions = AttributionSerializer(many=True, allow_empty=False)


class MatriceDroitsView(APIView):
    """
    Matrice des droits : catalogue, roles, et attributions en vigueur.

    `GET` sert a construire l'ecran ; `PUT` enregistre les cases modifiees.
    """

    permission_classes = [PeutGererComptes]

    @extend_schema(responses={200: None})
    def get(self, request: Request) -> Response:
        accordees = {
            (a.role, a.permission)
            for a in RolePermission.objects.all()
        }
        libelles = dict(Permission.choices)

        return Response(
            {
                "roles": [
                    {
                        "code": code,
                        "libelle": libelle,
                        "utilisateurs": User.objects.filter(role=code).count(),
                    }
                    for code, libelle in Role.choices
                ],
                "categories": [
                    {
                        "titre": titre,
                        "permissions": [
                            {
                                "code": code,
                                "libelle": libelles[code],
                                "roles": {
                                    role: {
                                        "accordee": (role, code) in accordees,
                                        "verrouillee": est_verrouillee(role, code),
                                    }
                                    for role, _ in Role.choices
                                },
                            }
                            for code in codes
                        ],
                    }
                    for titre, codes in CATEGORIES.items()
                ],
            }
        )

    @extend_schema(request=MatriceSerializer, responses={200: None})
    def put(self, request: Request) -> Response:
        serializer = MatriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attributions = serializer.validated_data["attributions"]

        # Une permission verrouillee ne se retire pas : retirer la gestion des
        # comptes a l'administration enfermerait tout le monde dehors, sans
        # moyen de revenir en arriere depuis l'interface.
        bloquees = [
            f"{a['role']}/{a['permission']}"
            for a in attributions
            if not a["accordee"] and est_verrouillee(a["role"], a["permission"])
        ]
        if bloquees:
            raise ValidationError(
                {
                    "attributions": (
                        "لا يمكن سحب هذه الصلاحيات، وإلا تعذّرت إدارة النظام: "
                        + ", ".join(bloquees)
                    )
                }
            )

        ajoutees, retirees = 0, 0
        with transaction.atomic():
            for attribution in attributions:
                role = attribution["role"]
                permission = attribution["permission"]
                if attribution["accordee"]:
                    _, cree = RolePermission.objects.get_or_create(
                        role=role,
                        permission=permission,
                        defaults={"granted_by": request.user},
                    )
                    ajoutees += int(cree)
                else:
                    supprimees, _ = RolePermission.objects.filter(
                        role=role, permission=permission
                    ).delete()
                    retirees += supprimees

        if ajoutees or retirees:
            audit.info(
                "Droits modifies par %s : %d accordee(s), %d retiree(s) — %s",
                request.user.username,
                ajoutees,
                retirees,
                ", ".join(
                    f"{a['role']}/{a['permission']}={'+' if a['accordee'] else '-'}"
                    for a in attributions
                ),
            )

        return Response(
            {"accordees": ajoutees, "retirees": retirees},
            status=status.HTTP_200_OK,
        )


class ExceptionSerializer(serializers.Serializer):
    """Une exception individuelle a poser, ou a lever."""

    permission = serializers.ChoiceField(choices=Permission.choices)
    #: `null` leve l'exception : la personne repasse sous le regime de son role.
    granted = serializers.BooleanField(allow_null=True, required=False, default=None)
    reason = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default=""
    )


class ExceptionsUtilisateurSerializer(serializers.Serializer):
    exceptions = ExceptionSerializer(many=True, allow_empty=False)


def _etat_permissions(utilisateur: User) -> list[dict]:
    """Pour chaque permission : ce que dit le role, et l'exception eventuelle."""
    du_role = utilisateur.permissions_du_role()
    exceptions = {
        e.permission: e
        for e in UserPermission.objects.filter(user=utilisateur)
    }
    libelles = dict(Permission.choices)

    lignes = []
    for code in Permission.values:
        exception = exceptions.get(code)
        lignes.append(
            {
                "code": code,
                "libelle": libelles[code],
                "par_le_role": code in du_role,
                "exception": None if exception is None else exception.granted,
                "raison": exception.reason if exception else "",
                "effective": (
                    exception.granted if exception is not None else code in du_role
                ),
            }
        )
    return lignes


class UtilisateursDroitsView(APIView):
    """
    Personnes auxquelles on peut confier une capacite individuelle.

    Les etudiantes sont exclues : leurs droits tiennent a leur statut, pas a
    une delegation.
    """

    permission_classes = [PeutGererComptes]

    @extend_schema(responses={200: None})
    def get(self, request: Request) -> Response:
        recherche = (request.query_params.get("search") or "").strip()
        personnes = User.objects.exclude(role=Role.STUDENT).filter(is_active=True)
        if recherche:
            personnes = personnes.filter(
                Q(username__icontains=recherche)
                | Q(full_name_ar__icontains=recherche)
            )

        exceptions = {}
        for exception in UserPermission.objects.filter(user__in=personnes):
            exceptions.setdefault(exception.user_id, []).append(exception)

        return Response(
            [
                {
                    "id": personne.id,
                    "username": personne.username,
                    "full_name_ar": personne.full_name_ar,
                    "role": personne.role,
                    "role_display": personne.get_role_display(),
                    "exceptions": [
                        {"permission": e.permission, "granted": e.granted}
                        for e in exceptions.get(personne.id, [])
                    ],
                }
                for personne in personnes.order_by("role", "full_name_ar")[:200]
            ]
        )


class DroitsUtilisateurView(APIView):
    """Etat detaille et modification des droits d'une personne."""

    permission_classes = [PeutGererComptes]

    @extend_schema(responses={200: None})
    def get(self, request: Request, pk: int) -> Response:
        utilisateur = get_object_or_404(User, pk=pk)
        return Response(
            {
                "id": utilisateur.id,
                "username": utilisateur.username,
                "full_name_ar": utilisateur.full_name_ar,
                "role": utilisateur.role,
                "role_display": utilisateur.get_role_display(),
                "permissions": _etat_permissions(utilisateur),
            }
        )

    @extend_schema(request=ExceptionsUtilisateurSerializer, responses={200: None})
    def put(self, request: Request, pk: int) -> Response:
        utilisateur = get_object_or_404(User, pk=pk)
        if utilisateur.role == Role.STUDENT:
            raise ValidationError(
                "الصلاحيات الفردية لا تُمنح للطالبات."
            )
        # L'administration a tout : une exception n'aurait aucun effet, et une
        # exception restrictive donnerait l'illusion d'avoir retire un droit.
        if utilisateur.is_admin_role:
            raise ValidationError(
                "المدير يملك جميع الصلاحيات؛ لا تُسجَّل عليه استثناءات."
            )

        serializer = ExceptionsUtilisateurSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        posees, levees = 0, 0
        with transaction.atomic():
            for exception in serializer.validated_data["exceptions"]:
                code = exception["permission"]
                granted = exception.get("granted")
                if granted is None:
                    supprimees, _ = UserPermission.objects.filter(
                        user=utilisateur, permission=code
                    ).delete()
                    levees += supprimees
                    continue

                UserPermission.objects.update_or_create(
                    user=utilisateur,
                    permission=code,
                    defaults={
                        "granted": granted,
                        "reason": exception.get("reason", ""),
                        "granted_by": request.user,
                    },
                )
                posees += 1

        audit.info(
            "Droits individuels — %s : %d exception(s) posee(s), %d levee(s), par %s",
            utilisateur.username,
            posees,
            levees,
            request.user.username,
        )
        return Response(
            {
                "posees": posees,
                "levees": levees,
                "permissions": _etat_permissions(utilisateur),
            }
        )
