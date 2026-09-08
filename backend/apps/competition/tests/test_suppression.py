"""
Qui peut effacer une session.

Animer un concours et l'effacer ne sont pas le meme geste. Le premier se
rattrape ; le second emporte les groupes, les tours et les decisions du jury —
la seule trace de ce qui s'est passe dans la salle. La permission
`competition.animer` se delegue a un membre du jury : elle ne doit pas ouvrir
cette porte-la.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from rest_framework import status

from apps.competition import services
from apps.competition.models import Competition, Group

from .test_concours import animateur, api_jury  # noqa: F401  (fixtures)


def _concours(par) -> Competition:
    competition = Competition.objects.create(
        name="مسابقة القرآن", code=services.generer_code(), created_by=par
    )
    for i in range(2):
        Group.objects.create(
            competition=competition, name=f"المجموعة {i + 1}", display_order=i
        )
    return competition


@pytest.mark.django_db
def test_l_administration_supprime_une_session(api, admin_user, animateur) -> None:
    competition = _concours(par=animateur)
    api.force_authenticate(admin_user)

    reponse = api.delete(reverse("competition-detail", args=[competition.id]))

    assert reponse.status_code == status.HTTP_204_NO_CONTENT
    assert not Competition.objects.filter(pk=competition.pk).exists()


@pytest.mark.django_db
def test_le_jury_ne_supprime_pas(api_jury, animateur) -> None:
    """Conduire un concours n'autorise pas a l'effacer."""
    competition = _concours(par=animateur)

    reponse = api_jury.delete(reverse("competition-detail", args=[competition.id]))

    assert reponse.status_code == status.HTTP_403_FORBIDDEN
    assert Competition.objects.filter(pk=competition.pk).exists()


@pytest.mark.django_db
def test_le_jury_garde_le_reste_de_la_route(api_jury, animateur) -> None:
    """
    Le verrou porte sur la suppression seule.

    Un `get_permissions` mal ecrit fermerait toute la ressource au jury, qui
    ne pourrait plus preparer ni conduire quoi que ce soit.
    """
    competition = _concours(par=animateur)

    lecture = api_jury.get(reverse("competition-detail", args=[competition.id]))
    depart = api_jury.post(
        reverse("competition-demarrer", args=[competition.id]), format="json"
    )

    assert lecture.status_code == status.HTTP_200_OK
    assert depart.status_code == status.HTTP_400_BAD_REQUEST  # pas assez de questions
