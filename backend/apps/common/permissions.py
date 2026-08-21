"""
Permissions transverses.

Deux regles de conception :

1. **L'autorisation repose sur des codes de permission**, pas sur le nom du
   role. Un role est une etiquette ; ce qui ouvre une porte, c'est une
   capacite explicitement accordee. Retirer une permission a un role la
   retire partout — interface et API en meme temps.

2. **Le filtrage se fait au niveau du queryset**, pas seulement a
   l'affichage. Ces classes bloquent l'acces a une route ; c'est le
   `get_queryset` de chaque vue qui garantit qu'un utilisateur ne voit que ce
   qui le concerne, meme en forgeant une URL.
"""

from __future__ import annotations

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.rbac import Permission


class HasPermission(permissions.BasePermission):
    """
    Exige une permission precise.

    S'utilise en la specialisant :

        class MaVue(APIView):
            permission_classes = [RequiresPermission(Permission.NOTES_SAISIR)]
    """

    code: str = ""
    message = "لا تملك الصلاحية اللازمة لهذه العملية."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.has_perm_code(self.code)


def RequiresPermission(code: str) -> type[HasPermission]:  # noqa: N802
    """Fabrique une classe de permission liee a un code du catalogue."""
    return type(
        f"Requires_{code.replace('.', '_')}",
        (HasPermission,),
        {"code": code},
    )


class ReadOnlyOrPermission(permissions.BasePermission):
    """
    Lecture pour tout utilisateur authentifie, ecriture sous condition de
    permission.

    Utilise pour les referentiels : sections, matieres, annees. Le contenu
    reste filtre par le queryset de la vue.
    """

    code: str = ""
    message = "لا تملك الصلاحية اللازمة لهذه العملية."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return user.has_perm_code(self.code)


def ReadOnlyOrRequires(code: str) -> type[ReadOnlyOrPermission]:  # noqa: N802
    return type(
        f"ReadOnlyOr_{code.replace('.', '_')}",
        (ReadOnlyOrPermission,),
        {"code": code},
    )


# --------------------------------------------------------------------------
# Raccourcis pour les usages les plus frequents
# --------------------------------------------------------------------------

PeutSaisirNotes = RequiresPermission(Permission.NOTES_SAISIR)
PeutConsulterNotes = RequiresPermission(Permission.NOTES_CONSULTER)

#: Lire une grille de notes.
#:
#: Saisir suppose de lire : quelqu'un qui n'a que `notes.saisir` doit pouvoir
#: ouvrir sa grille et son avancement, sans pour autant acceder aux
#: classements de section, qui relevent de `notes.consulter`.
PeutVoirLaSaisie = PeutSaisirNotes | PeutConsulterNotes
PeutDeliberer = RequiresPermission(Permission.DELIBERATION_GERER)
PeutGererStructure = RequiresPermission(Permission.STRUCTURE_GERER)
PeutGererEtudiantes = RequiresPermission(Permission.ETUDIANTES_GERER)
PeutGererAnnees = RequiresPermission(Permission.ANNEES_GERER)
PeutConsulterJournal = RequiresPermission(Permission.JOURNAL_CONSULTER)
PeutGererComptes = RequiresPermission(Permission.COMPTES_GERER)

LectureOuStructure = ReadOnlyOrRequires(Permission.STRUCTURE_GERER)
LectureOuEtudiantes = ReadOnlyOrRequires(Permission.ETUDIANTES_GERER)
LectureOuAnnees = ReadOnlyOrRequires(Permission.ANNEES_GERER)


class IsAdmin(permissions.BasePermission):
    """
    Reserve au personnel administratif.

    Conserve pour les operations qui tiennent au statut, pas a une capacite
    metier — par exemple l'acces au back-office technique.
    """

    message = "هذه العملية مخصصة للإدارة."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role)


class MustHaveChangedPassword(permissions.BasePermission):
    """
    Bloque toute route metier tant que le mot de passe temporaire n'a pas ete
    remplace. Seules les routes d'authentification y echappent.
    """

    message = "يجب تغيير كلمة السر قبل متابعة الاستخدام."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return not user.must_change_password
