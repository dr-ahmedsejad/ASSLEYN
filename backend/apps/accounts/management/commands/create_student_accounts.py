"""
Creation en lot des comptes etudiantes.

Chaque etudiante recoit un identifiant egal a son matricule et, pour premier
mot de passe, **ce meme matricule ecrit deux fois** — 24060 ouvre avec
2406024060. Le changement est impose des la premiere connexion.

    python manage.py create_student_accounts --dry-run
    python manage.py create_student_accounts

La regle etant connue de tous, aucun fichier n'est necessaire. `--output`
reste disponible pour produire la liste, mais elle contient des mots de passe
en clair : a imprimer, distribuer, puis detruire — jamais a conserver ni a
versionner.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, Student, User

def mot_de_passe_initial(matricule: str) -> str:
    """
    Mot de passe de premiere connexion : le matricule ecrit deux fois.

    Regle fixee par l'etablissement. Elle a un merite decisif sur un tirage
    aleatoire : aucune feuille de mots de passe a imprimer, a distribuer et a
    detruire. Chaque etudiante connait deja son numero, et le changement est
    impose des la premiere connexion.

    Ce mot de passe n'a donc de valeur que le temps d'une ouverture de
    session. C'est aussi pour cela qu'il n'est pas soumis aux validateurs :
    `set_password` ne les appelle pas, et il n'y a rien a valider dans un
    identifiant destine a etre remplace tout de suite.
    """
    return f"{matricule}{matricule}"


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

                mot_de_passe = mot_de_passe_initial(etudiante.matricule)
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
                writer.writerow(["رقم الطالبة", "الاسم الكامل", "كلمة السر الأولى"])
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
