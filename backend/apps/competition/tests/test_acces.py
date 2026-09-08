"""
Qui peut faire quoi sur un concours.

Un catalogue de permissions bien redige ne prouve rien : ce qui compte est ce
que repond chaque route. Ce fichier les frappe toutes, avec quatre profils, et
constate. Une route ajoutee sans garde apparaitra ici comme un acces accorde a
quelqu'un qui ne devrait pas l'avoir.

Trois regles se lisent dans les resultats :

- **l'ecran de la salle est la seule route ouverte.** C'est un lien qu'on
  projette ou qu'on partage ; demander un compte a une assemblee n'aurait
  aucun sens ;
- **conduire un concours tient a `competition.animer`**, une permission
  delegable — le jury n'est pas forcement l'administration ;
- **ouvrir, effacer et ecrire les enonces restent a l'administration.**
  Animer, c'est conduire : constituer les equipes, lancer, trancher. Decider
  qu'il y aura un concours engage l'institut ; effacer celui qui a eu lieu
  emporte la seule trace de ce qui s'est passe dans la salle ; et les enonces
  sont le fond du concours — qui anime les decouvre en meme temps que la
  salle.
"""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import Role, RolePermission, User
from apps.accounts.rbac import Permission
from apps.competition import services
from apps.competition.models import Competition, Group, Question

from .test_concours import animateur  # noqa: F401  (fixture)

#: Un refus, quel que soit son habillage. DRF rend 403 pour une session
#: absente comme pour un droit manquant.
REFUS = {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


@pytest.fixture
def sans_droits(db) -> User:
    """
    Un compte authentifie qui n'a rien a voir avec les concours.

    Le role est celui d'un enseignant, et non de l'assistance : la fixture du
    jury accorde `competition.animer` a **tout le role** ASSISTANT, si bien
    qu'un temoin pris dans ce role aurait herite du droit qu'on veut lui voir
    refuser.
    """
    user = User.objects.create_user(
        username="prof", password="MotDePasse2026", full_name_ar="أستاذة"
    )
    user.role = Role.TEACHER
    user.save(update_fields=["role"])
    # Un droit reel, mais pas celui-ci : etre connecte et servir a quelque
    # chose ne donne pas acces aux concours.
    RolePermission.objects.get_or_create(
        role=Role.TEACHER, permission=Permission.NOTES_SAISIR
    )
    return user


@pytest.fixture
def concours(animateur) -> Competition:
    competition = Competition.objects.create(
        name="مسابقة القرآن", code=services.generer_code(), created_by=animateur
    )
    for i in range(2):
        Group.objects.create(
            competition=competition, name=f"المجموعة {i + 1}", display_order=i
        )
    for i in range(4):
        Question.objects.create(
            competition=competition, text=f"السؤال {i + 1}", display_order=i
        )
    return competition


def _routes(competition: Competition, tour_id: int) -> list[tuple[str, str, dict]]:
    """Les routes de conduite : celles que `competition.animer` doit ouvrir."""
    return [
        ("get", reverse("competition-list"), {}),
        ("get", reverse("competition-detail", args=[competition.id]), {}),
        ("post", reverse("competition-ajouter-groupe", args=[competition.id]), {"name": "ج"}),
        ("get", reverse("competition-deroule", args=[competition.id]), {}),
        ("post", reverse("competition-demarrer", args=[competition.id]), {}),
        ("post", reverse("competition-barrage", args=[competition.id]), {}),
        ("post", reverse("competition-cloturer", args=[competition.id]), {}),
        ("post", reverse("tour-lancer", args=[tour_id]), {"client_uuid": str(uuid.uuid4())}),
        (
            "post",
            reverse("tour-decider", args=[tour_id]),
            {"client_uuid": str(uuid.uuid4()), "outcome": "CORRECT"},
        ),
    ]


def _routes_reservees(competition: Competition) -> list[tuple[str, str, dict]]:
    """Ce que la permission du jury ne doit pas donner."""
    return [
        ("post", reverse("competition-list"), {"name": "أخرى"}),
        ("delete", reverse("competition-detail", args=[competition.id]), {}),
        (
            "patch",
            reverse("competition-detail", args=[competition.id]),
            {"questions_reservees": 4},
        ),
        (
            "post",
            reverse("competition-ajouter-questions", args=[competition.id]),
            {"textes": ["سؤال"]},
        ),
    ]


def _appeler(client, methode: str, url: str, corps: dict):
    return getattr(client, methode)(url, corps, format="json")


# --------------------------------------------------------------------------
# Ce qui est ferme
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_aucune_route_du_jury_n_est_ouverte(api, concours) -> None:
    """
    Sans compte, tout est refuse.

    Le test parcourt les routes une a une : celle qu'on ajouterait sans garde
    apparaitrait ici, et nulle part ailleurs avant la mise en service.
    """
    services.demarrer(concours)
    tour = concours.turns.first()

    for methode, url, corps in _routes(concours, tour.id):
        reponse = _appeler(api, methode, url, corps)
        assert reponse.status_code in REFUS, f"{methode.upper()} {url} est ouverte"

    for methode, url, corps in _routes_reservees(concours):
        reponse = _appeler(api, methode, url, corps)
        assert reponse.status_code in REFUS, f"{methode.upper()} {url} est ouverte"


@pytest.mark.django_db
def test_un_compte_sans_la_permission_est_refuse(api, sans_droits, concours) -> None:
    """Etre connecte ne suffit pas : il faut `competition.animer`."""
    services.demarrer(concours)
    tour = concours.turns.first()
    api.force_authenticate(sans_droits)

    for methode, url, corps in _routes(concours, tour.id) + _routes_reservees(
        concours
    ):
        reponse = _appeler(api, methode, url, corps)
        assert reponse.status_code in REFUS, f"{methode.upper()} {url} passe sans droit"


# --------------------------------------------------------------------------
# Ce qui est ouvert
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_l_ecran_de_la_salle_reste_ouvert_a_tous(api, concours) -> None:
    """
    La seule route sans compte de toute l'application.

    C'est un lien qu'on projette ou qu'on partage : demander une connexion a
    une assemblee n'aurait aucun sens. Elle ne rend donc que ce qui est fait
    pour etre vu.
    """
    services.demarrer(concours)

    reponse = api.get(reverse("ecran-public", args=[concours.code]))

    assert reponse.status_code == status.HTTP_200_OK
    assert "classement" in reponse.data


@pytest.mark.django_db
def test_la_permission_suffit_a_conduire_un_concours(api, animateur, concours) -> None:
    """
    `competition.animer` se delegue : le jury n'est pas l'administration.

    Aucune de ces routes ne doit reclamer davantage — sans quoi la permission
    serait decorative et l'administration devrait tenir la tablette elle-meme.
    """
    services.demarrer(concours)
    tour = concours.turns.first()
    api.force_authenticate(animateur)

    for methode, url, corps in _routes(concours, tour.id):
        reponse = _appeler(api, methode, url, corps)
        assert reponse.status_code not in REFUS, f"{methode.upper()} {url} est refusee"


# --------------------------------------------------------------------------
# Ce qui reste a l'administration
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_jury_n_ouvre_ni_n_efface_une_session(
    api, animateur, admin_user, concours
) -> None:
    """
    `competition.animer` conduit un concours ; elle ne l'ecrit pas.

    Le jury recoit une session deja creee, avec ses enonces, la mene de bout
    en bout, et ne peut ni la faire disparaitre ni changer ce sur quoi les
    etudiantes sont evaluees.
    """
    api.force_authenticate(animateur)
    refus = [
        _appeler(api, methode, url, corps)
        for methode, url, corps in _routes_reservees(concours)
    ]

    assert all(r.status_code == status.HTTP_403_FORBIDDEN for r in refus)
    assert Competition.objects.filter(pk=concours.pk).exists()


@pytest.mark.django_db
def test_l_administration_ouvre_ecrit_et_efface(api, admin_user, concours) -> None:
    api.force_authenticate(admin_user)

    accordes = [
        _appeler(api, methode, url, corps)
        for methode, url, corps in _routes_reservees(concours)
        if methode != "delete"
    ]
    suppression = api.delete(reverse("competition-detail", args=[concours.id]))

    assert all(r.status_code not in REFUS for r in accordes)
    assert suppression.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_l_administration_n_a_pas_besoin_qu_on_lui_accorde_la_permission(
    api, admin_user, concours
) -> None:
    """
    Retirer la ligne ne lui retire pas le droit.

    L'attribution existe en base — les defauts la creent — mais elle n'est pas
    ce qui fait autorite : l'administration dispose de toutes les capacites
    par construction. C'est elle qui repare quand la matrice des droits est
    mal reglee, et un droit qu'elle pourrait perdre l'enfermerait dehors.

    On efface donc la ligne, et on verifie que rien ne change.
    """
    RolePermission.objects.filter(
        role=Role.ADMIN, permission=Permission.COMPETITION_ANIMER
    ).delete()

    api.force_authenticate(admin_user)
    reponse = api.get(reverse("competition-deroule", args=[concours.id]))

    assert admin_user.has_perm_code(Permission.COMPETITION_ANIMER)
    assert reponse.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_la_permission_figure_dans_la_matrice_des_droits(api, admin_user) -> None:
    """
    Une permission absente de la matrice ne se delegue pas.

    Elle existerait dans le code, garderait des routes, et resterait
    introuvable pour qui voudrait l'accorder — un droit invisible vaut un
    droit inexistant.
    """
    api.force_authenticate(admin_user)

    matrice = api.get(reverse("rbac-matrice")).data
    codes = {
        permission["code"]
        for categorie in matrice["categories"]
        for permission in categorie["permissions"]
    }

    assert Permission.COMPETITION_ANIMER in codes
