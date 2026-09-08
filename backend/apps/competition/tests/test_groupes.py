"""
Composition des groupes importee d'un classeur.

Ces listes disent qui compose une equipe le temps d'une seance. Les
participantes ne se connectent pas et rien dans l'application ne leur est
rattache : le nom depose est tout ce qu'on garde, et tout ce dont on a besoin.

Ce qui se verifie ici : qu'un classeur ordinaire — nom de groupe repete,
ligne d'en-tete, second depot pour completer — donne la composition attendue,
et qu'aucun nom ne se perd en chemin.
"""

from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook
from rest_framework import status

from apps.competition import classeur, services
from apps.competition.models import Competition, Group, GroupMember, Question

from .test_concours import animateur, api_jury  # noqa: F401  (fixtures)


def _classeur(lignes: list[tuple]) -> bytes:
    livre = Workbook()
    feuille = livre.active
    for ligne in lignes:
        feuille.append(list(ligne))
    tampon = io.BytesIO()
    livre.save(tampon)
    return tampon.getvalue()


def _concours(par) -> Competition:
    return Competition.objects.create(
        name="مسابقة القرآن", code=services.generer_code(), created_by=par
    )


def _deposer(api, competition, contenu: bytes, nom: str = "groupes.xlsx"):
    return api.post(
        reverse("competition-importer-groupes", args=[competition.id]),
        {"fichier": SimpleUploadedFile(nom, contenu)},
        format="multipart",
    )


# --------------------------------------------------------------------------
# Constitution des groupes
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_classeur_cree_les_groupes_et_leurs_listes(animateur) -> None:
    competition = _concours(par=animateur)

    crees, inscrites = services.importer_groupes(
        competition,
        [
            ("نور اليقين", "سارة بن علي"),
            ("نور اليقين", "مريم قاسمي"),
            ("رياض الصالحات", "خديجة عمراني"),
        ],
    )
    groupes = list(competition.groups.order_by("display_order"))

    assert (crees, inscrites) == (2, 3)
    assert [g.name for g in groupes] == ["نور اليقين", "رياض الصالحات"]
    assert [m.name for m in groupes[0].members.all()] == [
        "سارة بن علي",
        "مريم قاسمي",
    ]
    assert groupes[1].members.count() == 1


@pytest.mark.django_db
def test_les_groupes_recoivent_des_couleurs_distinctes(animateur) -> None:
    """Un groupe se reconnait a sa couleur avant que son nom se lise."""
    competition = _concours(par=animateur)

    services.importer_groupes(
        competition, [("أ", ""), ("ب", ""), ("ج", ""), ("د", "")]
    )
    couleurs = [g.color for g in competition.groups.order_by("display_order")]

    assert couleurs == list(services.COULEURS_GROUPES[:4])
    assert len(set(couleurs)) == 4


@pytest.mark.django_db
def test_un_groupe_deja_present_est_complete(animateur) -> None:
    """On depose la liste d'une classe, puis celle d'une autre."""
    competition = _concours(par=animateur)
    Group.objects.create(competition=competition, name="نور اليقين", display_order=0)

    crees, inscrites = services.importer_groupes(
        competition, [("نور اليقين", "سارة بن علي")]
    )

    assert (crees, inscrites) == (0, 1)
    assert competition.groups.count() == 1


@pytest.mark.django_db
def test_un_nom_depose_deux_fois_ne_compte_qu_une(animateur) -> None:
    """Un classeur se redepose souvent, corrige d'une ligne."""
    competition = _concours(par=animateur)

    services.importer_groupes(competition, [("نور اليقين", "سارة بن علي")])
    _, inscrites = services.importer_groupes(
        competition, [("نور اليقين", "سارة بن علي"), ("نور اليقين", "مريم قاسمي")]
    )

    assert inscrites == 1
    assert GroupMember.objects.filter(group__competition=competition).count() == 2


@pytest.mark.django_db
def test_un_groupe_sans_membre_reste_valable(animateur) -> None:
    """On inscrit une equipe avant d'en connaitre la composition."""
    competition = _concours(par=animateur)

    crees, inscrites = services.importer_groupes(competition, [("نور اليقين", "")])

    assert (crees, inscrites) == (1, 0)
    assert competition.groups.count() == 1


@pytest.mark.django_db
def test_le_nom_est_pris_tel_quel(animateur) -> None:
    """
    Aucune correspondance n'est cherchee dans le fichier des etudiantes.

    Ces participantes ne se connectent pas : un rattachement n'apporterait
    rien, et son absence passerait pour une anomalie alors qu'elle est la
    regle.
    """
    competition = _concours(par=animateur)

    services.importer_groupes(competition, [("نور اليقين", "زينب من معهد آخر")])
    membre = GroupMember.objects.get(group__competition=competition)

    assert membre.name == "زينب من معهد آخر"


# --------------------------------------------------------------------------
# Le fichier depose dans le mauvais import
# --------------------------------------------------------------------------


def test_un_classeur_de_questions_est_refuse_par_l_import_des_groupes() -> None:
    """
    Le defaut qui a coute une preparation entiere.

    Les deux depots se ressemblent — deux colonnes, un bouton — et le fichier
    des questions est parti dans celui des groupes. Les trois enonces sont
    devenus trois equipes, leurs reponses trois participantes, et la seance
    n'a pas pu demarrer faute de questions. Rien n'avait proteste.

    La ligne d'en-tete est le seul signe fiable : elle nomme les colonnes.
    """
    contenu = _classeur(
        [
            ("السؤال", "الإجابة"),
            ("كم عدد سور القرآن الكريم؟", "مئة وأربع عشرة سورة."),
        ]
    )

    with pytest.raises(classeur.ClasseurInvalide) as erreur:
        classeur.lire_groupes(contenu)
    assert "مجموعات" in str(erreur.value)


def test_un_classeur_de_groupes_est_refuse_par_l_import_des_questions() -> None:
    """Le meme controle dans l'autre sens."""
    contenu = _classeur([("المجموعة", "الطالبة"), ("نور اليقين", "سارة بن علي")])

    with pytest.raises(classeur.ClasseurInvalide) as erreur:
        classeur.lire(contenu)
    assert "أسئلة" in str(erreur.value)


def test_un_classeur_sans_entete_reste_accepte() -> None:
    """
    Le controle porte sur l'en-tete, pas sur le contenu.

    Beaucoup de gens n'en mettent pas : refuser leur fichier faute de pouvoir
    l'identifier serait pire que le probleme qu'on evite.
    """
    couples = classeur.lire_groupes(
        _classeur([("نور اليقين", "سارة بن علي"), ("رياض الصالحات", "مريم قاسمي")])
    )

    assert len(couples) == 2


@pytest.mark.django_db
def test_la_route_refuse_le_mauvais_classeur(api_jury, animateur) -> None:
    competition = _concours(par=animateur)

    reponse = _deposer(
        api_jury,
        competition,
        _classeur([("السؤال", "الإجابة"), ("سؤال أول", "جواب أول")]),
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.groups.count() == 0


# --------------------------------------------------------------------------
# La route
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_depot_rend_le_compte_de_ce_qui_a_ete_cree(api_jury, animateur) -> None:
    competition = _concours(par=animateur)

    reponse = _deposer(
        api_jury,
        competition,
        _classeur(
            [
                ("المجموعة", "الطالبة"),
                ("نور اليقين", "سارة بن علي"),
                ("نور اليقين", "مريم قاسمي"),
                ("رياض الصالحات", "خديجة عمراني"),
            ]
        ),
    )

    assert reponse.status_code == status.HTTP_201_CREATED
    assert reponse.data["groupes"] == 2
    assert reponse.data["membres"] == 3


@pytest.mark.django_db
def test_le_depot_est_refuse_apres_le_depart(api_jury, animateur) -> None:
    competition = _concours(par=animateur)
    services.importer_groupes(competition, [("أ", ""), ("ب", "")])
    for i in range(2):
        Question.objects.create(
            competition=competition, text=f"سؤال {i}", display_order=i
        )
    services.demarrer(competition)

    reponse = _deposer(api_jury, competition, _classeur([("ج", "")]))

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.groups.count() == 2


@pytest.mark.django_db
def test_l_ecran_de_la_salle_annonce_la_composition(api, animateur) -> None:
    """La salle voit qui repond — c'est le sens meme de ces listes."""
    competition = _concours(par=animateur)
    services.importer_groupes(
        competition,
        [
            ("نور اليقين", "سارة بن علي"),
            ("نور اليقين", "مريم قاسمي"),
            ("رياض الصالحات", "خديجة عمراني"),
        ],
    )
    for i in range(2):
        Question.objects.create(
            competition=competition, text=f"سؤال {i}", display_order=i
        )
    services.demarrer(competition)

    corps = api.get(reverse("ecran-public", args=[competition.code])).data

    assert corps["tour"]["group_name"] == "نور اليقين"
    assert corps["tour"]["group_members"] == ["سارة بن علي", "مريم قاسمي"]
