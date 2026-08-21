"""
Import du programme d'un فصل depuis un fichier JSON.

Le fichier decrit, pour une annee et un فصل, les matieres de chaque قسم et
leur coefficient. La commande cree les matieres manquantes au catalogue, puis
pose les programmes.

    python manage.py importer_programme programmes/fasl2-2025-2026.json --dry-run
    python manage.py importer_programme programmes/fasl2-2025-2026.json

Idempotente : la relancer met a jour les coefficients sans creer de doublon.

Une matiere retiree du fichier est **desactivee**, jamais supprimee : elle peut
deja porter des notes, et l'historique d'un فصل ne se reecrit pas.

Format attendu :

    {
      "year": "2025-2026",
      "semester": 2,
      "subjects": [{"code": "SAWM", "name_ar": "الصوم"}],
      "programmes": [
        {
          "section": "ALIMAT",
          "matieres": [{"subject": "QURAN", "coefficient": 5}]
        }
      ]
    }
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Section,
    Semester,
    SemesterState,
    Subject,
)


class Command(BaseCommand):
    help = "Importe le programme d'un فصل (matieres et coefficients) depuis un JSON."

    def add_arguments(self, parser) -> None:
        parser.add_argument("source", type=Path, help="Fichier JSON du programme.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyse et affiche le resultat sans rien ecrire.",
        )
        parser.add_argument(
            "--garder-absentes",
            action="store_true",
            help=(
                "Ne desactive pas les matieres absentes du fichier "
                "(par defaut elles sont desactivees)."
            ),
        )

    def handle(self, *args, **options) -> None:
        source: Path = options["source"]
        if not source.exists():
            raise CommandError(f"Fichier introuvable : {source}")

        donnees = json.loads(source.read_text(encoding="utf-8"))

        try:
            year = AcademicYear.objects.get(label=donnees["year"])
        except AcademicYear.DoesNotExist as erreur:
            raise CommandError(
                f"Annee inconnue : {donnees['year']}"
            ) from erreur

        try:
            semester = Semester.objects.get(year=year, number=donnees["semester"])
        except Semester.DoesNotExist as erreur:
            raise CommandError(
                f"Fasl {donnees['semester']} introuvable pour {year.label}."
            ) from erreur

        if semester.state == SemesterState.PUBLISHED:
            raise CommandError(
                "Les resultats de ce fasl sont publies : le programme ne peut "
                "plus etre modifie. Repassez le fasl en etat CLOSED d'abord."
            )

        catalogue = {s.code: s for s in Subject.objects.all()}
        sections = {s.code: s for s in Section.objects.all()}

        # --- Verifications avant toute ecriture ---------------------------
        erreurs: list[str] = []
        a_creer: list[dict] = []
        for matiere in donnees.get("subjects", []):
            if matiere["code"] not in catalogue:
                a_creer.append(matiere)

        codes_connus = set(catalogue) | {m["code"] for m in a_creer}
        for bloc in donnees["programmes"]:
            if bloc["section"] not in sections:
                erreurs.append(f"Section inconnue : {bloc['section']}")
            for ligne in bloc["matieres"]:
                if ligne["subject"] not in codes_connus:
                    erreurs.append(
                        f"Matiere absente du catalogue et du fichier : "
                        f"{ligne['subject']} ({bloc['section']})"
                    )
                try:
                    if Decimal(str(ligne["coefficient"])) <= 0:
                        erreurs.append(
                            f"Coefficient nul ou negatif : {ligne['subject']}"
                        )
                except (InvalidOperation, TypeError):
                    erreurs.append(
                        f"Coefficient illisible : {ligne['subject']} "
                        f"= {ligne['coefficient']!r}"
                    )

        if erreurs:
            for erreur in erreurs:
                self.stdout.write(self.style.ERROR(f"   {erreur}"))
            raise CommandError(f"{len(erreurs)} erreur(s) : rien n'a ete ecrit.")

        self.stdout.write(f"\nAnnee {year.label} — الفصل {semester.number}")
        if a_creer:
            self.stdout.write(
                self.style.WARNING(f"\n{len(a_creer)} matiere(s) a creer :")
            )
            for matiere in a_creer:
                self.stdout.write(f"   {matiere['code']:<14} {matiere['name_ar']}")

        if options["dry_run"]:
            self._apercu(donnees, sections)
            self.stdout.write(self.style.WARNING("\n--dry-run : rien n'a ete ecrit."))
            return

        with transaction.atomic():
            stats = self._importer(
                donnees, year, semester, a_creer, options["garder_absentes"]
            )

        self.stdout.write(self.style.SUCCESS("\nImport termine."))
        for cle, valeur in stats.items():
            self.stdout.write(f"   {cle:<22} : {valeur}")
        self._apercu(donnees, sections)
        self.stdout.write(
            "\nPensez a ouvrir la saisie du fasl pour que les enseignants "
            "puissent entrer les notes."
        )

    # ------------------------------------------------------------------

    def _importer(
        self,
        donnees: dict,
        year: AcademicYear,
        semester: Semester,
        a_creer: list[dict],
        garder_absentes: bool,
    ) -> dict[str, int]:
        stats = {
            "matieres creees": 0,
            "programmes crees": 0,
            "coefficients modifies": 0,
            "matieres reactivees": 0,
            "matieres desactivees": 0,
        }

        rang = Subject.objects.count()
        for matiere in a_creer:
            Subject.objects.create(
                code=matiere["code"],
                name_ar=matiere["name_ar"],
                display_order=matiere.get("display_order", rang),
            )
            rang += 1
            stats["matieres creees"] += 1

        catalogue = {s.code: s for s in Subject.objects.all()}
        sections = {s.code: s for s in Section.objects.all()}

        for bloc in donnees["programmes"]:
            section = sections[bloc["section"]]
            voulues: set[int] = set()

            for ordre, ligne in enumerate(bloc["matieres"]):
                subject = catalogue[ligne["subject"]]
                voulues.add(subject.id)
                coefficient = Decimal(str(ligne["coefficient"]))

                programme, cree = Curriculum.objects.get_or_create(
                    section=section,
                    semester=semester,
                    subject=subject,
                    defaults={
                        "coefficient": coefficient,
                        "display_order": ordre,
                        "is_active": True,
                    },
                )
                if cree:
                    stats["programmes crees"] += 1
                    continue

                champs = []
                if programme.coefficient != coefficient:
                    programme.coefficient = coefficient
                    champs.append("coefficient")
                    stats["coefficients modifies"] += 1
                if not programme.is_active:
                    programme.is_active = True
                    champs.append("is_active")
                    stats["matieres reactivees"] += 1
                if programme.display_order != ordre:
                    programme.display_order = ordre
                    champs.append("display_order")
                if champs:
                    programme.save(update_fields=champs)

            if not garder_absentes:
                # Desactivation plutot que suppression : une matiere retiree
                # peut deja porter des notes.
                retirees = Curriculum.objects.filter(
                    section=section, semester=semester, is_active=True
                ).exclude(subject_id__in=voulues)
                stats["matieres desactivees"] += retirees.update(is_active=False)

        return stats

    def _apercu(self, donnees: dict, sections: dict) -> None:
        self.stdout.write("\nProgramme :")
        for bloc in donnees["programmes"]:
            section = sections.get(bloc["section"])
            nom = section.name_ar if section else bloc["section"]
            total = sum(Decimal(str(m["coefficient"])) for m in bloc["matieres"])
            self.stdout.write(
                f"\n   {nom} — {len(bloc['matieres'])} matieres, "
                f"total des coefficients : {total:g}"
            )
            for ligne in bloc["matieres"]:
                self.stdout.write(
                    f"      {ligne['subject']:<14} × {ligne['coefficient']}"
                )
