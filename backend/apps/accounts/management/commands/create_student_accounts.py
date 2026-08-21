"""
Creation en lot des comptes etudiantes.

Chaque etudiante recoit un identifiant egal a son matricule et un mot de passe
temporaire genere aleatoirement, qu'elle devra changer a sa premiere
connexion.

    python manage.py create_student_accounts --dry-run
    python manage.py create_student_accounts --output comptes.csv

Le fichier produit contient les mots de passe en clair : il est destine a etre
imprime, distribue, puis detruit. Il ne doit jamais etre conserve ni
versionne.
"""

from __future__ import annotations

import csv
import secrets
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, Student, User

# Alphabet sans caracteres ambigus (0/O, 1/l/I) : ces mots de passe sont
# recopies a la main depuis une feuille imprimee.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
LONGUEUR = 12


def mot_de_passe_temporaire() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LONGUEUR))


class Command(BaseCommand):
    help = "Cree les comptes des etudiantes qui n'en ont pas encore."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run", action="store_true", help="Affiche sans rien creer."
        )
        parser.add_argument(
            "--output",
            type=Path,
            help="Fichier CSV ou ecrire les identifiants (mots de passe en clair).",
        )
        parser.add_argument(
            "--section", help="Limiter a une section, par son code."
        )

    def handle(self, *args, **options) -> None:
        candidates = Student.objects.filter(user__isnull=True, is_active=True)
        if options.get("section"):
            candidates = candidates.filter(
                enrollments__section__code=options["section"], enrollments__is_active=True
            )
        candidates = candidates.order_by("matricule")

        if not candidates.exists():
            self.stdout.write(
                self.style.SUCCESS("Toutes les etudiantes ont deja un compte.")
            )
            return

        self.stdout.write(f"{candidates.count()} compte(s) a creer.")
        if options["dry_run"]:
            for etudiante in candidates:
                self.stdout.write(f"   {etudiante.matricule} — {etudiante.full_name_ar}")
            self.stdout.write(self.style.WARNING("--dry-run : rien n'a ete cree."))
            return

        crees: list[tuple[str, str, str]] = []
        with transaction.atomic():
            for etudiante in candidates:
                if User.objects.filter(username=etudiante.matricule).exists():
                    self.stdout.write(
                        self.style.WARNING(
                            f"Identifiant deja pris, ignore : {etudiante.matricule}"
                        )
                    )
                    continue

                mot_de_passe = mot_de_passe_temporaire()
                user = User.objects.create_user(
                    username=etudiante.matricule,
                    password=mot_de_passe,
                    full_name_ar=etudiante.full_name_ar,
                )
                user.role = Role.STUDENT
                user.must_change_password = True
                user.save(update_fields=["role", "must_change_password"])

                etudiante.user = user
                etudiante.save(update_fields=["user"])
                crees.append(
                    (etudiante.matricule, etudiante.full_name_ar, mot_de_passe)
                )

        self.stdout.write(self.style.SUCCESS(f"{len(crees)} compte(s) cree(s)."))

        if options.get("output"):
            chemin: Path = options["output"]
            with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
                writer = csv.writer(fichier)
                writer.writerow(["رقم الطالبة", "الاسم الكامل", "كلمة السر المؤقتة"])
                writer.writerows(crees)
            self.stdout.write(
                self.style.WARNING(
                    f"\nIdentifiants ecrits dans {chemin}.\n"
                    "Ce fichier contient des mots de passe en clair : imprimez-le, "
                    "distribuez-le, puis supprimez-le."
                )
            )
        else:
            self.stdout.write(
                "\nAucun fichier demande. Utilisez --output pour recuperer les "
                "mots de passe temporaires : ils ne sont pas recuperables ensuite."
            )
