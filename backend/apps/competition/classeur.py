"""
Lecture d'un classeur de questions.

Le format est le plus simple qu'on puisse demander a quelqu'un : deux
colonnes, la question puis la reponse, une ligne par question. Une ligne
d'en-tete est acceptee et ignoree — les gens en mettent une, et refuser le
fichier pour cela serait absurde.

Ce module ne connait ni Django ni HTTP : il prend des octets, il rend des
couples. C'est ce qui permet de le tester sans monter de requete.
"""

from __future__ import annotations

import io

from openpyxl import load_workbook

#: Au-dela, ce n'est plus un classeur de questions.
LIGNES_MAX = 2000

#: Mots qui trahissent une ligne d'en-tete, dans les deux langues qu'on
#: rencontre ici. Compares en minuscules, sans espaces autour.
ENTETES = {
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


class ClasseurInvalide(Exception):
    """Le fichier ne peut pas etre lu comme un classeur de questions."""


def _texte(valeur) -> str:
    """Une cellule vide, un nombre ou une date deviennent du texte propre."""
    if valeur is None:
        return ""
    return str(valeur).strip()


def _est_entete(question: str, reponse: str) -> bool:
    """
    La premiere ligne est-elle un intitule de colonne ?

    On ne se fie pas a la mise en forme — elle ne survit pas toujours a un
    export — mais au vocabulaire. Une vraie question porte un point
    d'interrogation ou depasse largement le mot isole.
    """
    return question.lower() in ENTETES or reponse.lower() in ENTETES


def lire(contenu: bytes) -> list[tuple[str, str]]:
    """
    Rend les couples (question, reponse) d'un classeur.

    Les lignes sans question sont ignorees : un classeur rempli a la main
    traine presque toujours des lignes vides en dessous, et s'arreter a la
    premiere ferait perdre ce qui suit.
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

        if rang == 0 and _est_entete(question, reponse):
            continue
        if not question:
            continue
        couples.append((question, reponse))

    classeur.close()

    if not couples:
        raise ClasseurInvalide("لم يُعثر على أي سؤال في الملف.")
    return couples
