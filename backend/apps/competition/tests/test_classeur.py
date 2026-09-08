"""
Import des questions depuis un classeur, et confinement des reponses.

Deux choses se jouent ici. La lecture du fichier, qui doit encaisser ce qu'un
tableur produit reellement — une ligne d'en-tete, des lignes vides, une
colonne de reponses absente. Et le confinement : la reponse existe pour le
jury, et l'ecran de la salle ne doit jamais la voir passer.
"""

from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook
from rest_framework import status

from apps.competition import classeur, services
from apps.competition.models import (
    Competition,
    CompetitionKind,
    Group,
    Question,
)

from .test_concours import animateur, api_jury  # noqa: F401  (fixtures)


def _classeur(lignes: list[tuple], titre: str = "الأسئلة") -> bytes:
    """Un classeur en memoire, tel qu'un tableur l'aurait ecrit."""
    livre = Workbook()
    feuille = livre.active
    feuille.title = titre
    for ligne in lignes:
        feuille.append(list(ligne))
    tampon = io.BytesIO()
    livre.save(tampon)
    return tampon.getvalue()


def _concours(par, kind=CompetitionKind.CULTURELLE) -> Competition:
    competition = Competition.objects.create(
        name="مسابقة القرآن",
        kind=kind,
        code=services.generer_code(),
        created_by=par,
    )
    for i in range(2):
        Group.objects.create(
            competition=competition, name=f"المجموعة {i + 1}", display_order=i
        )
    return competition


def _deposer(api, competition, contenu: bytes, nom: str = "questions.xlsx"):
    return api.post(
        reverse("competition-importer-questions", args=[competition.id]),
        {"fichier": SimpleUploadedFile(nom, contenu)},
        format="multipart",
    )


# --------------------------------------------------------------------------
# Lecture du classeur
# --------------------------------------------------------------------------


def test_deux_colonnes_donnent_question_et_reponse() -> None:
    contenu = _classeur([("كم عدد سور القرآن؟", "مئة وأربع عشرة سورة.")])

    assert classeur.lire(contenu) == [
        ("كم عدد سور القرآن؟", "مئة وأربع عشرة سورة.")
    ]


def test_la_ligne_d_entete_est_ignoree() -> None:
    """Les gens en mettent une. Refuser le fichier pour cela serait absurde."""
    contenu = _classeur(
        [
            ("السؤال", "الإجابة"),
            ("كم عدد سور القرآن؟", "مئة وأربع عشرة سورة."),
        ]
    )

    assert classeur.lire(contenu) == [
        ("كم عدد سور القرآن؟", "مئة وأربع عشرة سورة.")
    ]


def test_une_question_sans_reponse_est_acceptee() -> None:
    """La reponse est un aide-memoire, pas une condition."""
    contenu = _classeur([("كم عدد سور القرآن؟", None)])

    assert classeur.lire(contenu) == [("كم عدد سور القرآن؟", "")]


def test_les_lignes_vides_n_arretent_pas_la_lecture() -> None:
    """
    Un classeur rempli a la main en traine toujours.

    S'arreter a la premiere ligne vide ferait perdre en silence tout ce qui
    suit — et personne ne compterait les questions importees.
    """
    contenu = _classeur(
        [
            ("السؤال الأول", "الجواب الأول"),
            (None, None),
            ("السؤال الثاني", "الجواب الثاني"),
        ]
    )

    assert len(classeur.lire(contenu)) == 2


def test_un_fichier_illisible_est_refuse() -> None:
    with pytest.raises(classeur.ClasseurInvalide):
        classeur.lire(b"ceci n'est pas un classeur")


def test_un_classeur_sans_question_est_refuse() -> None:
    with pytest.raises(classeur.ClasseurInvalide):
        classeur.lire(_classeur([("السؤال", "الإجابة")]))


# --------------------------------------------------------------------------
# La route
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_le_depot_cree_les_questions_avec_leurs_reponses(
    api_jury, animateur
) -> None:
    competition = _concours(par=animateur)

    reponse = _deposer(
        api_jury,
        competition,
        _classeur(
            [
                ("السؤال", "الإجابة"),
                ("كم عدد سور القرآن؟", "مئة وأربع عشرة سورة."),
                ("من هي أول امرأة أسلمت؟", "خديجة بنت خويلد."),
            ]
        ),
    )
    questions = list(competition.questions.order_by("display_order"))

    assert reponse.status_code == status.HTTP_201_CREATED
    assert [q.text for q in questions] == [
        "كم عدد سور القرآن؟",
        "من هي أول امرأة أسلمت؟",
    ]
    assert questions[0].answer == "مئة وأربع عشرة سورة."


@pytest.mark.django_db
def test_un_second_depot_s_ajoute_au_premier(api_jury, animateur) -> None:
    """On complete un classeur par un autre, sans repartir de zero."""
    competition = _concours(par=animateur)

    _deposer(api_jury, competition, _classeur([("الأول", "أ")]))
    _deposer(api_jury, competition, _classeur([("الثاني", "ب")]))
    ordres = list(
        competition.questions.order_by("display_order").values_list(
            "display_order", flat=True
        )
    )

    assert competition.questions.count() == 2
    assert ordres == [0, 1]


@pytest.mark.django_db
def test_un_fichier_qui_n_est_pas_xlsx_est_refuse(api_jury, animateur) -> None:
    competition = _concours(par=animateur)

    reponse = _deposer(api_jury, competition, b"colonne;colonne", nom="questions.csv")

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.questions.count() == 0


@pytest.mark.django_db
def test_le_depot_est_refuse_sur_une_ndwa(api_jury, animateur) -> None:
    competition = _concours(par=animateur, kind=CompetitionKind.POETIQUE)

    reponse = _deposer(api_jury, competition, _classeur([("سؤال", "جواب")]))

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.questions.count() == 0


@pytest.mark.django_db
def test_le_depot_est_refuse_apres_le_depart(api_jury, animateur) -> None:
    competition = _concours(par=animateur)
    Question.objects.create(competition=competition, text="سؤال", display_order=0)
    Question.objects.create(competition=competition, text="سؤال آخر", display_order=1)
    services.demarrer(competition)

    reponse = _deposer(api_jury, competition, _classeur([("جديد", "جواب")]))

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert competition.questions.count() == 2


# --------------------------------------------------------------------------
# Confinement de la reponse
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_la_reponse_ne_sort_jamais_par_l_ecran_de_la_salle(
    api, api_jury, animateur
) -> None:
    """
    Le point de tout ce dispositif.

    La reponse est un aide-memoire pour qui anime. L'ecran de la salle est
    ouvert a tous, sans compte : si la reponse y passait, la competition
    n'aurait plus d'objet.
    """
    competition = _concours(par=animateur)
    Question.objects.create(
        competition=competition,
        text="كم عدد سور القرآن؟",
        answer="مئة وأربع عشرة سورة.",
        display_order=0,
    )
    Question.objects.create(
        competition=competition,
        text="من هي أول امرأة أسلمت؟",
        answer="خديجة بنت خويلد.",
        display_order=1,
    )
    services.demarrer(competition)

    salle = str(api.get(reverse("ecran-public", args=[competition.code])).data)

    assert "كم عدد سور القرآن؟" in salle  # l'enonce, lui, est projete
    assert "مئة وأربع عشرة سورة." not in salle
    assert "خديجة بنت خويلد." not in salle


@pytest.mark.django_db
def test_la_console_du_jury_recoit_la_reponse(api_jury, animateur) -> None:
    competition = _concours(par=animateur)
    Question.objects.create(
        competition=competition,
        text="كم عدد سور القرآن؟",
        answer="مئة وأربع عشرة سورة.",
        display_order=0,
    )
    Question.objects.create(
        competition=competition, text="سؤال آخر", answer="", display_order=1
    )
    services.demarrer(competition)

    corps = api_jury.get(reverse("competition-deroule", args=[competition.id])).data

    assert corps["tours"][0]["question_answer"] == "مئة وأربع عشرة سورة."
    # Une question sans reponse ne fabrique pas une chaine vide a afficher.
    assert corps["tours"][1]["question_answer"] is None
