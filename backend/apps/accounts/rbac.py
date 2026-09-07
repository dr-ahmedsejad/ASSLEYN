"""
Catalogue des permissions et attributions par role.

Le catalogue est declare **en code** : chaque code correspond a une capacite
reellement branchee sur des endpoints. Une permission qu'on pourrait creer a
la volee depuis une interface n'ouvrirait rien — elle donnerait l'illusion
d'un droit.

Ce qui est **en base**, et donc modifiable par l'administration, c'est
l'attribution : quel role recoit quelle permission (`RolePermission`).
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class Permission(models.TextChoices):
    """Capacites du systeme. Chaque code garde un endpoint et une entree de menu."""

    TABLEAU_CONSULTER = "tableau.consulter", _("لوحة القيادة")
    NOTES_SAISIR = "notes.saisir", _("إدخال النقاط")
    NOTES_CONSULTER = "notes.consulter", _("الاطلاع على النقاط والنتائج")
    DELIBERATION_GERER = "deliberation.gerer", _("المداولة والعتبات والنشر")
    STRUCTURE_GERER = "structure.gerer", _("البنية البيداغوجية والضوارب")
    ETUDIANTES_GERER = "etudiantes.gerer", _("ملفات الطالبات والتسجيل")
    ANNEES_GERER = "annees.gerer", _("السنوات الدراسية")
    JOURNAL_CONSULTER = "journal.consulter", _("السجلات والزيارات")
    COMPTES_GERER = "comptes.gerer", _("الحسابات والصلاحيات")
    COMPETITION_ANIMER = "competition.animer", _("إدارة المسابقات")
    RESULTATS_PERSONNELS = "resultats.personnels", _("الاطلاع على نتائجها")


#: Regroupement pour l'affichage de la matrice des droits.
CATEGORIES: dict[str, list[str]] = {
    "عام": [
        Permission.TABLEAU_CONSULTER,
    ],
    "التقويم": [
        Permission.NOTES_SAISIR,
        Permission.NOTES_CONSULTER,
        Permission.DELIBERATION_GERER,
    ],
    "الإدارة": [
        Permission.STRUCTURE_GERER,
        Permission.ETUDIANTES_GERER,
        Permission.ANNEES_GERER,
    ],
    "المتابعة": [
        Permission.JOURNAL_CONSULTER,
        Permission.COMPTES_GERER,
    ],
    "المسابقات": [
        Permission.COMPETITION_ANIMER,
    ],
    "الطالبة": [
        Permission.RESULTATS_PERSONNELS,
    ],
}


#: Attributions initiales. Elles servent d'amorcage : une fois en base,
#: l'administration les modifie sans toucher au code.
DEFAUTS: dict[str, tuple[str, ...]] = {
    "ADMIN": tuple(Permission.values),
    # L'assistance saisit les notes, et rien d'autre : son ecran est le poste
    # de saisie. Elargir son perimetre se fait depuis la matrice des droits.
    "ASSISTANT": (Permission.NOTES_SAISIR,),
    "TEACHER": (
        Permission.TABLEAU_CONSULTER,
        Permission.NOTES_SAISIR,
        Permission.NOTES_CONSULTER,
    ),
    "STUDENT": (Permission.RESULTATS_PERSONNELS,),
}


#: Permissions qu'un role ne peut pas perdre.
#:
#: L'administration dispose de **toutes** les capacites, sans exception et sans
#: possibilite de s'en priver : c'est elle qui repare quand quelque chose est
#: mal configure. Lui retirer un droit — a commencer par la gestion des
#: comptes — enfermerait tout le monde dehors sans moyen de revenir en
#: arriere depuis l'interface.
VERROUILLEES: dict[str, frozenset[str]] = {
    "ADMIN": frozenset(Permission.values),
}


def permissions_par_defaut(role: str) -> tuple[str, ...]:
    return DEFAUTS.get(role, ())


def est_verrouillee(role: str, permission: str) -> bool:
    return permission in VERROUILLEES.get(role, frozenset())
