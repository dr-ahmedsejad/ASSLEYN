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
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import password_validation

from apps.accounts.models import (
    Lockout,
    Role,
    RolePermission,
    Student,
    User,
    UserPermission,
)
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


class CreationCompteSerializer(serializers.Serializer):
    """
    Ouverture d'un compte.

    Le nom complet est **saisi**, jamais deduit de l'identifiant. Un
    identifiant est une chaine technique — `sejad`, `ahmed` — et le
    translitterer en arabe produit une orthographe approximative que
    l'interieresse ne reconnait pas comme la sienne.

    Pour une etudiante, le nom existe deja dans son dossier : on le reprend
    tel quel plutot que de le retaper, au risque d'une seconde orthographe.
    """

    #: Rattachement a un dossier d'etudiante. Present, il fournit a lui seul
    #: l'identifiant, le nom et le mot de passe initial.
    matricule = serializers.CharField(required=False, allow_blank=True)

    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    full_name_ar = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(
        required=False, allow_blank=True, style={"input_type": "password"}
    )
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=30)

    def validate(self, attrs: dict) -> dict:
        matricule = (attrs.get("matricule") or "").strip()

        if matricule:
            etudiante = Student.objects.filter(matricule=matricule).first()
            if etudiante is None:
                raise ValidationError({"matricule": "لا توجد طالبة بهذا الرقم."})
            if etudiante.user_id is not None:
                raise ValidationError({"matricule": "لهذه الطالبة حساب مسبقا."})

            attrs["etudiante"] = etudiante
            attrs["username"] = matricule
            attrs["full_name_ar"] = etudiante.full_name_ar
            attrs["role"] = Role.STUDENT
            # Regle de l'etablissement : le matricule ecrit deux fois.
            attrs["password"] = (attrs.get("password") or "").strip() or matricule * 2
        else:
            attrs["etudiante"] = None
            if attrs.get("role") == Role.STUDENT:
                raise ValidationError(
                    {"matricule": "حساب الطالبة يُنشأ من ملفها: أدخل رقم الطالبة."}
                )
            requis = {
                "username": "اسم المستخدم مطلوب.",
                "full_name_ar": "الاسم الكامل مطلوب.",
                "password": "كلمة السر مطلوبة.",
                "role": "الدور مطلوب.",
            }
            manquants = {
                champ: message
                for champ, message in requis.items()
                if not str(attrs.get(champ) or "").strip()
            }
            if manquants:
                raise ValidationError(manquants)

        attrs["username"] = attrs["username"].strip()
        attrs["full_name_ar"] = attrs["full_name_ar"].strip()

        if User.objects.filter(username__iexact=attrs["username"]).exists():
            raise ValidationError({"username": "اسم المستخدم مستعمل."})

        return attrs

    def validate_password(self, value: str) -> str:
        # Le mot de passe rattache a un matricule est valide dans `validate`,
        # ou l'on connait le compte vise. Ici on ne verifie que ce qui est
        # saisi librement.
        if value:
            password_validation.validate_password(value)
        return value


class CompteSerializer(serializers.ModelSerializer):
    """Une ligne de la liste des comptes."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    matricule = serializers.SerializerMethodField()
    verrouille = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name_ar",
            "role",
            "role_display",
            "matricule",
            "phone",
            "is_active",
            "must_change_password",
            "last_login",
            "date_joined",
            "verrouille",
        ]

    def get_matricule(self, obj: User) -> str | None:
        dossier = getattr(obj, "student_profile", None)
        return dossier.matricule if dossier else None

    def get_verrouille(self, obj: User) -> bool:
        return obj.username in self.context.get("verrouilles", set())


class IdentiteSerializer(serializers.Serializer):
    """Identite d'un compte, modifiable apres coup."""

    full_name_ar = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_full_name_ar(self, value: str) -> str:
        nom = value.strip()
        if not nom:
            raise ValidationError("الاسم الكامل مطلوب.")
        return nom


class UtilisateursDroitsView(APIView):
    """
    Personnes auxquelles on peut confier une capacite individuelle.

    Les etudiantes sont exclues de la **liste** : leurs droits tiennent a leur
    statut, pas a une delegation. Elles peuvent en revanche etre creees ici,
    a partir de leur dossier.
    """

    permission_classes = [PeutGererComptes]

    @extend_schema(request=CreationCompteSerializer, responses={201: None})
    def post(self, request: Request) -> Response:
        serializer = CreationCompteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data

        with transaction.atomic():
            utilisateur = User.objects.create_user(
                username=donnees["username"],
                password=donnees["password"],
                full_name_ar=donnees["full_name_ar"],
            )
            utilisateur.role = donnees["role"]
            utilisateur.phone = donnees.get("phone", "")
            # Le mot de passe pose par l'administration est provisoire, quelle
            # que soit sa qualite : il a transite par une autre personne.
            utilisateur.must_change_password = True
            utilisateur.save(update_fields=["role", "phone", "must_change_password"])

            etudiante = donnees["etudiante"]
            if etudiante is not None:
                etudiante.user = utilisateur
                etudiante.save(update_fields=["user"])

        audit.warning(
            "Compte cree — %s (%s, %s) par %s",
            utilisateur.username,
            utilisateur.full_name_ar,
            utilisateur.role,
            request.user.username,
        )
        return Response(
            {
                "id": utilisateur.id,
                "username": utilisateur.username,
                "full_name_ar": utilisateur.full_name_ar,
                "role": utilisateur.role,
                "role_display": utilisateur.get_role_display(),
                # Rendu une seule fois : il n'est stocke nulle part en clair.
                "mot_de_passe": donnees["password"],
            },
            status=status.HTTP_201_CREATED,
        )

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


class ComptesView(ListAPIView):
    """
    Tous les comptes, etudiantes comprises.

    A ne pas confondre avec `UtilisateursDroitsView`, qui ne montre que le
    personnel : celle-la sert a **deleguer une capacite**, et les droits d'une
    etudiante tiennent a son statut, pas a une delegation. Ici on regarde les
    comptes eux-memes — qui en a un, sous quel nom, ouvert ou ferme.

    Filtres : `search` (identifiant ou nom), `role`, `verrouilles=1`,
    `mdp_provisoire=1`.
    """

    serializer_class = CompteSerializer
    permission_classes = [PeutGererComptes]

    def get_queryset(self):
        comptes = User.objects.select_related("student_profile")

        recherche = (self.request.query_params.get("search") or "").strip()
        if recherche:
            comptes = comptes.filter(
                Q(username__icontains=recherche)
                | Q(full_name_ar__icontains=recherche)
            )

        role = self.request.query_params.get("role")
        if role in Role.values:
            comptes = comptes.filter(role=role)

        if self.request.query_params.get("mdp_provisoire") == "1":
            comptes = comptes.filter(must_change_password=True)

        if self.request.query_params.get("verrouilles") == "1":
            fermes = Lockout.objects.filter(
                released_at__isnull=True, until__gt=timezone.now()
            ).values("username")
            comptes = comptes.filter(username__in=fermes)

        # Le personnel d'abord : c'est lui qu'on cherche le plus souvent, et
        # les etudiantes se retrouvent par leur numero.
        return comptes.order_by("role", "username")

    def get_serializer_context(self) -> dict:
        contexte = super().get_serializer_context()
        # Une seule requete pour l'ensemble de la page, plutot qu'une par
        # ligne : c'est la difference entre 25 requetes et une.
        contexte["verrouilles"] = set(
            Lockout.objects.filter(
                released_at__isnull=True, until__gt=timezone.now()
            ).values_list("username", flat=True)
        )
        return contexte


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

    @extend_schema(request=IdentiteSerializer, responses={200: None})
    def patch(self, request: Request, pk: int) -> Response:
        """
        Corrige l'identite d'un compte : nom complet, telephone.

        Necessaire parce que les premiers comptes ont ete ouverts sans champ
        de nom, avec une translitteration de l'identifiant. Une personne doit
        pouvoir porter son nom tel qu'elle l'ecrit.
        """
        utilisateur = get_object_or_404(User, pk=pk)
        serializer = IdentiteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        modifies = []
        for champ, valeur in serializer.validated_data.items():
            if getattr(utilisateur, champ) != valeur:
                setattr(utilisateur, champ, valeur)
                modifies.append(champ)
        if modifies:
            utilisateur.save(update_fields=modifies)
            audit.info(
                "Identite modifiee — %s : %s par %s",
                utilisateur.username,
                ", ".join(modifies),
                request.user.username,
            )

            # Le nom d'une etudiante vit dans son dossier : le laisser diverger
            # de celui de son compte donnerait deux verites pour une personne.
            if "full_name_ar" in modifies:
                Student.objects.filter(user=utilisateur).update(
                    full_name_ar=utilisateur.full_name_ar
                )

        return Response(
            {
                "id": utilisateur.id,
                "username": utilisateur.username,
                "full_name_ar": utilisateur.full_name_ar,
                "phone": utilisateur.phone,
                "role": utilisateur.role,
                "role_display": utilisateur.get_role_display(),
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
