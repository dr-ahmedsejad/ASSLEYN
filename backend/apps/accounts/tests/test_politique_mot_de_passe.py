"""
Politique de mot de passe.

Huit caracteres au minimum, **numerique autorise** : le mot de passe de
premiere connexion d'une etudiante est son matricule ecrit deux fois. Ce qui
protege un mot de passe si court n'est pas sa longueur mais le verrouillage
progressif — cinq essais, puis la porte se ferme.

Les messages sont verifies en arabe : Django laisse celui de la longueur en
anglais, ce qui posait un avertissement anglais au milieu d'un ecran arabe.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import Role, User


def _messages(mot_de_passe: str) -> list[str]:
    try:
        password_validation.validate_password(mot_de_passe)
    except ValidationError as erreur:
        return list(erreur.messages)
    return []


@pytest.mark.parametrize(
    "mot_de_passe",
    ["24060240", "2406024060", "97531864", "MotDePasse2026"],
)
def test_mots_de_passe_acceptes(mot_de_passe: str) -> None:
    """Huit caracteres suffisent, et huit chiffres aussi."""
    assert _messages(mot_de_passe) == []


@pytest.mark.parametrize("mot_de_passe", ["1234", "abc", "2406024"])
def test_trop_court_refuse_en_arabe(mot_de_passe: str) -> None:
    messages = _messages(mot_de_passe)

    assert messages, f"{mot_de_passe} aurait du etre refuse"
    assert any("كلمة السر قصيرة" in m for m in messages)
    # Le message de Django reste en anglais : il ne doit plus apparaitre.
    assert not any("too short" in m for m in messages)


def test_mot_de_passe_courant_refuse_en_arabe() -> None:
    messages = _messages("12345678")

    assert any("شائعة" in m for m in messages)
    assert not any("too common" in m for m in messages)


@pytest.mark.django_db
def test_changer_pour_huit_chiffres(api) -> None:
    """Le parcours reel : une etudiante remplace son mot de passe initial."""
    etudiante = User.objects.create_user(
        username="24060", password="2406024060", full_name_ar="الدودو حسن"
    )
    etudiante.role = Role.STUDENT
    etudiante.must_change_password = True
    etudiante.save(update_fields=["role", "must_change_password"])
    api.force_authenticate(etudiante)

    reponse = api.post(
        reverse("auth-change-password"),
        {"current_password": "2406024060", "new_password": "24060240"},
        format="json",
    )

    assert reponse.status_code == status.HTTP_204_NO_CONTENT
    etudiante.refresh_from_db()
    assert etudiante.check_password("24060240")
    assert etudiante.must_change_password is False


@pytest.mark.django_db
def test_le_refus_est_rendu_en_arabe(api) -> None:
    etudiante = User.objects.create_user(
        username="24061", password="2406124061", full_name_ar="طالبة"
    )
    api.force_authenticate(etudiante)

    reponse = api.post(
        reverse("auth-change-password"),
        {"current_password": "2406124061", "new_password": "123"},
        format="json",
    )

    assert reponse.status_code == status.HTTP_400_BAD_REQUEST
    assert any("كلمة السر قصيرة" in m for m in reponse.data["new_password"])
