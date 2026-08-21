"""Tests de la creation en lot des comptes etudiantes."""

from __future__ import annotations

import csv

import pytest
from django.core.management import call_command

from apps.accounts.models import Role, Student, User


@pytest.fixture
def sans_compte(db) -> list[Student]:
    return [
        Student.objects.create(matricule=f"2400{i}", full_name_ar=f"طالبة {i}")
        for i in range(1, 4)
    ]


@pytest.mark.django_db
def test_creation_des_comptes(sans_compte) -> None:
    call_command("create_student_accounts", verbosity=0)

    for etudiante in sans_compte:
        etudiante.refresh_from_db()
        assert etudiante.user is not None
        assert etudiante.user.username == etudiante.matricule
        assert etudiante.user.role == Role.STUDENT
        # Premiere connexion : le mot de passe temporaire doit etre remplace.
        assert etudiante.user.must_change_password is True


@pytest.mark.django_db
def test_mots_de_passe_tous_differents(sans_compte, tmp_path) -> None:
    fichier = tmp_path / "comptes.csv"
    call_command("create_student_accounts", "--output", str(fichier), verbosity=0)

    with fichier.open(encoding="utf-8-sig") as handle:
        lignes = list(csv.reader(handle))[1:]

    assert len(lignes) == 3
    mots_de_passe = [ligne[2] for ligne in lignes]
    assert len(set(mots_de_passe)) == 3
    assert all(len(m) == 12 for m in mots_de_passe)
    # Les mots de passe ne sont jamais stockes en clair en base.
    for matricule, _nom, mot_de_passe in lignes:
        user = User.objects.get(username=matricule)
        assert user.check_password(mot_de_passe)
        assert mot_de_passe not in user.password


@pytest.mark.django_db
def test_dry_run_ne_cree_rien(sans_compte) -> None:
    call_command("create_student_accounts", "--dry-run", verbosity=0)
    assert User.objects.filter(role=Role.STUDENT).count() == 0


@pytest.mark.django_db
def test_relance_ne_recree_pas(sans_compte) -> None:
    call_command("create_student_accounts", verbosity=0)
    avant = User.objects.count()
    call_command("create_student_accounts", verbosity=0)
    assert User.objects.count() == avant
