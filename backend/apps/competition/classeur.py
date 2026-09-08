"""
Lecture des classeurs deposes : les questions, et les groupes.

Le format est le plus simple qu'on puisse demander a quelqu'un : deux
colonnes, une ligne par entree. Une ligne d'en-tete est acceptee et ignoree —
les gens en mettent une, et refuser le fichier pour cela serait absurde.

Ce module ne connait ni Django ni HTTP : il prend des octets, il rend des
couples. C'est ce qui permet de le tester sans monter de requete.
"""

from __future__ import annotations

import io

from openpyxl import load_workbook

#: Au-dela, ce n'est plus un classeur de questions.
LIGNES_MAX = 2000

#: Intitules de colonne d'un classeur de questions.
#:
#: Ils servent deux fois : a sauter la ligne d'en-tete d'un classeur de
#: questions, et a **reconnaitre un classeur de questions depose dans l'import
#: des groupes**. Les deux depots se ressemblent — deux colonnes, un bouton —
#: et le fichier peut partir dans le mauvais. Sans ce controle, les enonces
#: deviennent des noms d'equipes en silence.
ENTETES_QUESTIONS = {
    "السؤال",
    "الأسئلة",
    "سؤال",
    "الإجابة",
    "الاجابة",
    "الجواب",
    "question",
    "questions",
    "reponse",
    "réponse",
    "answer",
}

#: Intitules de colonne d'un classeur de composition.
ENTETES_GROUPES = {
    "المجموعة",
    "المجموعات",
    "مجموعة",
    "الفريق",
    "الطالبة",
    "الطالبات",
    "الاسم",
    "groupe",
    "groupes",
    "equipe",
    "équipe",
    "étudiante",
    "etudiante",
    "nom",
    "group",
    "student",
}


class ClasseurInvalide(Exception):
    """Le fichier ne peut pas etre lu comme un classeur de questions."""


def _texte(valeur) -> str:
    """Une cellule vide, un nombre ou une date deviennent du texte propre."""
    if valeur is None:
        return ""
    return str(valeur).strip()


def _entete_de(premiere: str, seconde: str, mots: set[str]) -> bool:
    """
    La premiere ligne est-elle un intitule de ce vocabulaire ?

    On ne se fie pas a la mise en forme — elle ne survit pas toujours a un
    export — mais aux mots employes.
    """
    return premiere.lower() in mots or seconde.lower() in mots


def _couples(
    contenu: bytes,
    *,
    vide: str,
    attendus: set[str],
    etrangers: set[str],
    mauvais_fichier: str,
) -> list[tuple[str, str]]:
    """
    Rend les couples des deux premieres colonnes d'un classeur.

    Les lignes sans premiere colonne sont ignorees : un classeur rempli a la
    main traine presque toujours des lignes vides en dessous, et s'arreter a
    la premiere ferait perdre ce qui suit.

    Une ligne d'en-tete du **mauvais** vocabulaire arrete tout : c'est le seul
    signe fiable qu'un fichier est parti dans le mauvais depot, et le laisser
    passer transformerait des enonces en equipes sans que personne s'en
    apercoive avant la salle.
    """
    try:
        classeur = load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    except Exception as erreur:  # openpyxl leve des exceptions tres variees
        raise ClasseurInvalide(
            "تعذر فتح الملف. المتوقع ملف Excel بصيغة xlsx."
        ) from erreur

    feuille = classeur.active
    if feuille is None:
        raise ClasseurInvalide("الملف لا يحتوي على أي ورقة.")

    couples: list[tuple[str, str]] = []
    for rang, ligne in enumerate(feuille.iter_rows(max_col=2, values_only=True)):
        if rang >= LIGNES_MAX:
            break
        question = _texte(ligne[0] if len(ligne) > 0 else None)
        reponse = _texte(ligne[1] if len(ligne) > 1 else None)

        if rang == 0:
            if _entete_de(question, reponse, etrangers):
                classeur.close()
                raise ClasseurInvalide(mauvais_fichier)
            if _entete_de(question, reponse, attendus):
                continue
        if not question:
            continue
        couples.append((question, reponse))

    classeur.close()

    if not couples:
        raise ClasseurInvalide(vide)
    return couples


def lire(contenu: bytes) -> list[tuple[str, str]]:
    """Les couples (enonce, reponse) d'un classeur de questions."""
    return _couples(
        contenu,
        vide="لم يُعثر على أي سؤال في الملف.",
        attendus=ENTETES_QUESTIONS,
        etrangers=ENTETES_GROUPES,
        mauvais_fichier="هذا ملف مجموعات، لا ملف أسئلة. استعمل استيراد القوائم.",
    )


def lire_groupes(contenu: bytes) -> list[tuple[str, str]]:
    """
    Les couples (groupe, membre) d'un classeur de composition.

    Le groupe se repete d'une ligne a l'autre — c'est ainsi qu'un tableur se
    remplit. Un groupe sans membre reste valable : on inscrit une equipe avant
    d'en connaitre la composition.
    """
    return _couples(
        contenu,
        vide="لم يُعثر على أي مجموعة في الملف.",
        attendus=ENTETES_GROUPES,
        etrangers=ENTETES_QUESTIONS,
        mauvais_fichier="هذا ملف أسئلة، لا ملف مجموعات. استعمل استيراد الأسئلة.",
    )
