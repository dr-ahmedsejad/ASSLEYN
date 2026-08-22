"""
Validateurs de mot de passe, en arabe.

Django traduit une partie de ses messages, pas tous : le catalogue arabe rend
bien « كلمة المرور هذه شائعة جداً » pour un mot de passe trop courant, mais
laisse en anglais le message de longueur — il passe par `ngettext`, dont la
forme plurielle manque. Une etudiante voyait donc « This password is too
short » sur un ecran entierement arabe.

Ces validateurs portent leur texte, sans dependre d'un catalogue.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

#: Longueur minimale fixee par l'etablissement. Huit caracteres, chiffres
#: compris : c'est le verrouillage progressif qui protege le compte, pas la
#: longueur (cf. apps/accounts/verrouillage.py).
LONGUEUR_MINIMALE = 8


class LongueurMinimale:
    """Refuse un mot de passe trop court, en arabe."""

    def __init__(self, min_length: int = LONGUEUR_MINIMALE) -> None:
        self.min_length = min_length

    def validate(self, password: str, user=None) -> None:
        if len(password) < self.min_length:
            raise ValidationError(
                _("كلمة السر قصيرة: يجب أن تتكون من %(min)d رموز على الأقل.")
                % {"min": self.min_length},
                code="password_too_short",
                params={"min_length": self.min_length},
            )

    def get_help_text(self) -> str:
        return _("%(min)d رموز على الأقل. الأرقام وحدها مقبولة.") % {
            "min": self.min_length
        }


class PasTropCourant:
    """
    Ecarte les mots de passe les plus essayes au monde.

    S'appuie sur la liste de Django, dont il ne reprend que la verification :
    le message, lui, est le notre — pour qu'il tienne le meme langage que le
    reste de l'ecran.
    """

    def __init__(self) -> None:
        from django.contrib.auth.password_validation import CommonPasswordValidator

        self._interne = CommonPasswordValidator()

    def validate(self, password: str, user=None) -> None:
        try:
            self._interne.validate(password, user)
        except ValidationError as erreur:
            raise ValidationError(
                _("كلمة السر هذه شائعة جدا؛ اختر غيرها."),
                code="password_too_common",
            ) from erreur

    def get_help_text(self) -> str:
        return _("تجنب كلمات السر الشائعة مثل 12345678.")
