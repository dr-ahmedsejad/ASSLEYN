"""
Remise des mots de passe etudiantes a la regle de l'etablissement.

Le mot de passe de premiere connexion est le matricule ecrit deux fois, et le
changement est impose des l'ouverture de session.

    python manage.py reset_student_passwords --dry-run
    python manage.py reset_student_passwords
    python manage.py reset_student_passwords --tout

Par defaut, seules les etudiantes qui **n'ont jamais choisi** leur mot de passe
sont touchees. Celle qui en a deja pose un l'a fait pour une raison : le lui
reprendre la mettrait dehors sans prevenir. `--tout` passe outre, quand la
direction veut repartir de zero pour l'ensemble de la promotion.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.management.commands.create_student_accounts import (
    mot_de_passe_initial,
)
from apps.accounts.models import Role, Student


class Command(BaseCommand):
    help = "Remet le mot de passe des etudiantes a leur matricule ecrit deux fois."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run", action="store_true", help="Affiche sans rien ecrire."
        )
        parser.add_argument(
            "--tout",
            action="store_true",
            help="Inclut celles qui ont deja choisi leur mot de passe.",
        )
        parser.add_argument("--section", help="Limiter a une section, par son code.")

    def handle(self, *args, **options) -> None:
        etudiantes = Student.objects.filter(
            user__isnull=False, user__role=Role.STUDENT
        ).select_related("user")
        if options.get("section"):
            etudiantes = etudiantes.filter(
                enrollments__section__code=options["section"]
            )
        etudiantes = etudiantes.order_by("matricule")

        concernees, epargnees = [], []
        for etudiante in etudiantes:
            if etudiante.user.must_change_password or options["tout"]:
                concernees.append(etudiante)
            else:
                epargnees.append(etudiante)

        self.stdout.write(f"{len(concernees)} compte(s) a remettre a la regle.")
        if epargnees and not options["tout"]:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(epargnees)} compte(s) epargne(s) : mot de passe deja "
                    "choisi par l'etudiante. --tout pour les inclure."
                )
            )

        if options["dry_run"]:
            for etudiante in concernees:
                self.stdout.write(
                    f"   {etudiante.matricule} — {etudiante.full_name_ar} "
                    f"-> {mot_de_passe_initial(etudiante.matricule)}"
                )
            self.stdout.write(self.style.WARNING("\n--dry-run : rien n'a ete ecrit."))
            return

        with transaction.atomic():
            for etudiante in concernees:
                user = etudiante.user
                user.set_password(mot_de_passe_initial(etudiante.matricule))
                user.must_change_password = True
                user.password_changed_at = timezone.now()
                user.save(
                    update_fields=[
                        "password",
                        "must_change_password",
                        "password_changed_at",
                    ]
                )

        self.stdout.write(
            self.style.SUCCESS(f"\n{len(concernees)} mot(s) de passe remis a la regle.")
        )
        self.stdout.write(
            "Chaque etudiante ouvre avec son matricule ecrit deux fois, "
            "puis choisit le sien."
        )
