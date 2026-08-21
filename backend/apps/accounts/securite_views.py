"""
Surveillance des connexions.

Trois lectures et deux gestes :

- le **journal** de toutes les tentatives, reussies ou non, avec leur adresse ;
- les **statistiques de frequentation**, dont les dix etudiantes les plus
  assidues ;
- les **comptes bloques**, et de quoi les rouvrir ;
- la **reinitialisation** d'un mot de passe par l'administration.

Le journal se consulte avec `journal.consulter`. Debloquer un compte et
reinitialiser un mot de passe touchent aux acces : ces deux operations
relevent de `comptes.gerer`.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import verrouillage
from apps.accounts.models import Lockout, LoginAttempt, LoginOutcome, Role, User
from apps.accounts.serializers import (
    LockoutSerializer,
    LoginAttemptSerializer,
    ReinitialisationMotDePasseSerializer,
)
from apps.common.permissions import PeutConsulterJournal, PeutGererComptes

audit = logging.getLogger("asleyn.audit")

#: Periodes proposees par l'interface, en jours. `None` vaut « depuis toujours ».
PERIODES = {"7": 7, "30": 30, "90": 90, "tout": None}

#: Alphabet des mots de passe temporaires : ni 0/O ni 1/l/I. Ces mots de passe
#: sont recopies a la main depuis un ecran ou une feuille.
ALPHABET_TEMPORAIRE = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def _depuis(request: Request):
    """Borne basse de la periode demandee, ou `None`."""
    jours = PERIODES.get(request.query_params.get("periode", "30"), 30)
    return None if jours is None else timezone.now() - timedelta(days=jours)


class JournalConnexionsView(ListAPIView):
    """
    Journal des connexions.

    Filtres : `outcome`, `username`, `periode`, `succes=1|0`. La pagination
    est celle du reste de l'API.
    """

    serializer_class = LoginAttemptSerializer
    permission_classes = [PeutConsulterJournal]

    def get_queryset(self):
        lignes = LoginAttempt.objects.select_related("user").all()

        debut = _depuis(self.request)
        if debut is not None:
            lignes = lignes.filter(at__gte=debut)

        issue = self.request.query_params.get("outcome")
        if issue in LoginOutcome.values:
            lignes = lignes.filter(outcome=issue)

        succes = self.request.query_params.get("succes")
        if succes == "1":
            lignes = lignes.filter(outcome=LoginOutcome.SUCCESS)
        elif succes == "0":
            lignes = lignes.exclude(outcome=LoginOutcome.SUCCESS)

        recherche = self.request.query_params.get("username")
        if recherche:
            lignes = lignes.filter(username__icontains=recherche)

        return lignes


class StatistiquesVisitesView(APIView):
    """
    Frequentation.

    Une **visite** est une connexion reussie. C'est la seule definition qui se
    tienne ici : le navigateur ne joint jamais Django directement, il n'y a
    donc pas de page vue cote API a compter, et compter les requetes du serveur
    Next melerait le trafic technique a la consultation reelle.
    """

    permission_classes = [PeutConsulterJournal]

    @extend_schema(responses={200: None})
    def get(self, request: Request) -> Response:
        debut = _depuis(request)
        maintenant = timezone.now()

        visites = LoginAttempt.objects.filter(outcome=LoginOutcome.SUCCESS)
        if debut is not None:
            visites = visites.filter(at__gte=debut)

        aujourdhui = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)

        # Dix etudiantes les plus assidues. Le classement ne porte que sur les
        # comptes d'etudiantes : le personnel se connecte tous les jours, il
        # occuperait la totalite du tableau sans rien apprendre a personne.
        top = (
            visites.filter(user__role=Role.STUDENT)
            .values("user_id", "username", "user__full_name_ar")
            .annotate(visites=Count("id"), derniere=Max("at"))
            .order_by("-visites", "user__full_name_ar")[:10]
        )

        # Frequentation jour par jour, pour la courbe.
        par_jour = (
            visites.annotate(jour=TruncDate("at"))
            .values("jour")
            .annotate(visites=Count("id"))
            .order_by("jour")
        )

        echecs = LoginAttempt.objects.exclude(outcome=LoginOutcome.SUCCESS)
        if debut is not None:
            echecs = echecs.filter(at__gte=debut)

        return Response(
            {
                "periode": request.query_params.get("periode", "30"),
                "visites": visites.count(),
                "visiteurs": visites.values("username").distinct().count(),
                "visites_aujourdhui": LoginAttempt.objects.filter(
                    outcome=LoginOutcome.SUCCESS, at__gte=aujourdhui
                ).count(),
                "echecs": echecs.count(),
                "blocages": Lockout.objects.filter(
                    started_at__gte=debut
                ).count()
                if debut is not None
                else Lockout.objects.count(),
                "blocages_actifs": Lockout.objects.filter(
                    released_at__isnull=True, until__gt=maintenant
                ).count(),
                "top_etudiantes": [
                    {
                        "username": ligne["username"],
                        "full_name_ar": ligne["user__full_name_ar"] or "",
                        "visites": ligne["visites"],
                        "derniere": ligne["derniere"],
                    }
                    for ligne in top
                ],
                "par_jour": [
                    {"jour": ligne["jour"], "visites": ligne["visites"]}
                    for ligne in par_jour
                ],
            }
        )


class VerrousView(ListAPIView):
    """
    Comptes bloques.

    Par defaut, seuls les blocages **en cours** : c'est la liste sur laquelle
    l'administration agit. `?historique=1` ajoute les blocages echus et les
    deblocages passes, pour comprendre apres coup.
    """

    serializer_class = LockoutSerializer
    permission_classes = [PeutGererComptes]

    def get_queryset(self):
        verrous = Lockout.objects.select_related("user", "released_by")
        if self.request.query_params.get("historique") == "1":
            return verrous.all()
        return verrous.filter(released_at__isnull=True, until__gt=timezone.now())


class DeverrouillerView(APIView):
    """Rouvre un compte avant l'expiration de son blocage."""

    permission_classes = [PeutGererComptes]

    @extend_schema(request=None, responses={200: LockoutSerializer})
    def post(self, request: Request, pk: int) -> Response:
        verrou = get_object_or_404(Lockout, pk=pk)
        if verrou.released_at is not None:
            return Response(
                {"detail": "هذا الإقفال مفتوح مسبقا."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verrouillage.deverrouiller(verrou, par=request.user)
        audit.info(
            "Deblocage — compte=%s par=%s", verrou.username, request.user.username
        )
        return Response(LockoutSerializer(verrou).data)


class ReinitialiserMotDePasseView(APIView):
    """
    Reinitialisation d'un mot de passe par l'administration.

    L'ancien mot de passe n'est pas demande — l'administration intervient
    justement quand il est perdu. Le nouveau est **temporaire** : il est
    renvoye une seule fois, dans cette reponse, et son remplacement est impose
    a la premiere connexion.

    Toutes les sessions ouvertes du compte tombent, et un eventuel blocage est
    leve : reinitialiser sans rouvrir la porte n'aurait aucun sens.
    """

    permission_classes = [PeutGererComptes]

    @extend_schema(
        request=ReinitialisationMotDePasseSerializer, responses={200: None}
    )
    def post(self, request: Request, pk: int) -> Response:
        cible = get_object_or_404(User, pk=pk)
        serializer = ReinitialisationMotDePasseSerializer(
            data=request.data, context={"cible": cible}
        )
        serializer.is_valid(raise_exception=True)

        choisi = serializer.validated_data.get("new_password") or ""
        motdepasse = choisi or "".join(
            secrets.choice(ALPHABET_TEMPORAIRE) for _ in range(12)
        )

        cible.set_password(motdepasse)
        cible.must_change_password = True
        cible.password_changed_at = timezone.now()
        cible.save(
            update_fields=["password", "must_change_password", "password_changed_at"]
        )

        # Un mot de passe change doit fermer les sessions en cours : si le
        # compte a ete pris, l'intrus doit perdre la main immediatement.
        # Django invalide les sessions dont le hash ne correspond plus.
        leves = Lockout.objects.filter(
            username=cible.username, released_at__isnull=True, until__gt=timezone.now()
        )
        for verrou in leves:
            verrouillage.deverrouiller(verrou, par=request.user)

        audit.warning(
            "Reinitialisation de mot de passe — cible=%s par=%s genere=%s",
            cible.username,
            request.user.username,
            not choisi,
        )
        return Response(
            {
                "username": cible.username,
                "full_name_ar": cible.full_name_ar,
                # Renvoye une seule fois : il n'est stocke nulle part en clair.
                "mot_de_passe": motdepasse,
                "genere": not choisi,
                "verrous_leves": len(leves),
            }
        )
