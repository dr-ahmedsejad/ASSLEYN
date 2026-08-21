"""
Amorcage de l'annee 2025-2026 a partir des donnees reelles de l'institut.

Cree l'annee, ses deux فصول, les cinq sections, les huit matieres, les
programmes avec leurs coefficients, les etudiantes, leurs inscriptions et les
notes du فصل 1 — puis lance le calcul.

    python manage.py seed_2025_2026 --dry-run
    python manage.py seed_2025_2026

La commande est idempotente : la relancer ne cree pas de doublons.

Le matricule 24097 est attribue a deux etudiantes differentes dans le fichier
source, et n'apparait dans aucune liste officielle. Par defaut la seconde
occurrence est **refusee** et signalee : c'est a la direction d'attribuer un
matricule. L'option --provisional-matricules permet de l'importer malgre tout
avec un numero provisoire de la plage 99xxx.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    Section,
    Semester,
    SemesterState,
    Subject,
)
from apps.accounts.models import Student
from apps.grading.models import Grade, GradeStatus
from apps.results.services import default_rule_for, recompute_semester

DEFAULT_SOURCE = (
    Path(settings.BASE_DIR)
    / "apps"
    / "results"
    / "tests"
    / "fixtures"
    / "golden_fasl1_2025_2026.json"
)

YEAR_LABEL = "2025-2026"

SECTION_ORDER = ["ALIMAT", "HAFIZAT", "MURABBIYAT", "HAFIDAT", "MUTAMAYYIZAT"]

SUBJECT_NAMES = {
    "QURAN": "القرآن الكريم",
    "FIQH": "الفقه",
    "NAHW": "النحو",
    "LUGHA": "اللغة",
    "SIRA": "السيرة النبوية",
    "MAHARIM": "محارم اللسان",
    "AKHDARI": "الأخضري",
    "ABQARI": "العبقري",
}
SUBJECT_ORDER = list(SUBJECT_NAMES)

PROVISIONAL_START = 99001


class Command(BaseCommand):
    help = "Amorce l'annee 2025-2026 avec les donnees reelles de l'institut."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--source",
            type=Path,
            default=DEFAULT_SOURCE,
            help="Fichier JSON source (par defaut le jeu de reference du فصل 1).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyse et affiche le resume sans rien ecrire.",
        )
        parser.add_argument(
            "--provisional-matricules",
            action="store_true",
            help="Importe les matricules en conflit avec un numero provisoire 99xxx.",
        )

    def handle(self, *args, **options) -> None:
        source: Path = options["source"]
        if not source.exists():
            raise CommandError(f"Fichier source introuvable : {source}")

        payload = json.loads(source.read_text(encoding="utf-8"))
        sections = payload["sections"]

        conflits = self._detect_matricule_conflicts(sections)
        if conflits:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(conflits)} matricule(s) en conflit dans le fichier source :"
                )
            )
            for matricule, lignes in conflits.items():
                for ligne in lignes:
                    self.stdout.write(
                        f"   {matricule} — {ligne['full_name_ar']} "
                        f"({ligne['section']}, ligne {ligne['row']})"
                    )

        if options["dry_run"]:
            self._resume(sections, conflits)
            self.stdout.write(self.style.WARNING("\n--dry-run : rien n'a ete ecrit."))
            return

        with transaction.atomic():
            stats = self._importer(
                sections, conflits, options["provisional_matricules"]
            )
        self._rapport(stats, conflits, options["provisional_matricules"])

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------

    def _detect_matricule_conflicts(self, sections: list[dict]) -> dict[str, list[dict]]:
        vus: dict[str, list[dict]] = {}
        for section in sections:
            for student in section["students"]:
                vus.setdefault(student["matricule"], []).append(
                    {
                        "full_name_ar": student["full_name_ar"],
                        "section": section["name_ar"],
                        "row": student["row"],
                    }
                )
        return {m: lignes for m, lignes in vus.items() if len(lignes) > 1}

    def _resume(self, sections: list[dict], conflits: dict) -> None:
        total = sum(len(s["students"]) for s in sections)
        self.stdout.write("\nA importer :")
        self.stdout.write(f"   annee            : {YEAR_LABEL} (2 فصول)")
        self.stdout.write(f"   sections         : {len(sections)}")
        self.stdout.write(f"   matieres         : {len(SUBJECT_NAMES)}")
        self.stdout.write(f"   lignes etudiantes: {total}")
        self.stdout.write(f"   dont en conflit  : {sum(len(v) for v in conflits.values())}")
        for section in sections:
            coefs = " · ".join(
                f"{SUBJECT_NAMES[c]}×{coef}" for c, coef in section["coefficients"].items()
            )
            self.stdout.write(
                f"   - {section['name_ar']:<20} {len(section['students']):>3} etudiantes   {coefs}"
            )

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _importer(
        self, sections: list[dict], conflits: dict, provisoire: bool
    ) -> dict[str, int]:
        year, _ = AcademicYear.objects.get_or_create(
            label=YEAR_LABEL,
            defaults={
                "start_date": date(2025, 10, 1),
                "end_date": date(2026, 6, 30),
                "is_active": True,
            },
        )
        default_rule_for(year)

        fasl1, _ = Semester.objects.get_or_create(
            year=year,
            number=1,
            defaults={
                "start_date": date(2025, 10, 1),
                "end_date": date(2026, 1, 31),
                "state": SemesterState.OPEN,
                "weight": Decimal("1"),
            },
        )
        Semester.objects.get_or_create(
            year=year,
            number=2,
            defaults={
                "start_date": date(2026, 2, 1),
                "end_date": date(2026, 6, 30),
                "state": SemesterState.DRAFT,
                "weight": Decimal("1"),
            },
        )

        subjects = {
            code: Subject.objects.get_or_create(
                code=code,
                defaults={
                    "name_ar": name,
                    "display_order": SUBJECT_ORDER.index(code),
                },
            )[0]
            for code, name in SUBJECT_NAMES.items()
        }

        stats = {
            "sections": 0,
            "curricula": 0,
            "etudiantes": 0,
            "inscriptions": 0,
            "notes": 0,
            "absences": 0,
            "refusees": 0,
            "provisoires": 0,
        }
        prochaine_provisoire = PROVISIONAL_START
        deja_importes: set[str] = set()

        for bloc in sections:
            section, _ = Section.objects.get_or_create(
                code=bloc["code"],
                defaults={
                    "name_ar": bloc["name_ar"],
                    "display_order": SECTION_ORDER.index(bloc["code"])
                    if bloc["code"] in SECTION_ORDER
                    else 99,
                },
            )
            stats["sections"] += 1

            curricula: dict[str, Curriculum] = {}
            for ordre, (code, coef) in enumerate(bloc["coefficients"].items()):
                curriculum, _ = Curriculum.objects.get_or_create(
                    section=section,
                    semester=fasl1,
                    subject=subjects[code],
                    defaults={
                        "coefficient": Decimal(str(coef)),
                        "display_order": ordre,
                    },
                )
                curricula[code] = curriculum
                stats["curricula"] += 1

            for ligne in bloc["students"]:
                matricule = ligne["matricule"]
                if matricule in conflits and matricule in deja_importes:
                    if not provisoire:
                        stats["refusees"] += 1
                        continue
                    matricule = str(prochaine_provisoire)
                    prochaine_provisoire += 1
                    stats["provisoires"] += 1

                student, cree = Student.objects.get_or_create(
                    matricule=matricule,
                    defaults={"full_name_ar": ligne["full_name_ar"]},
                )
                deja_importes.add(ligne["matricule"])
                if cree:
                    stats["etudiantes"] += 1

                enrollment, cree = Enrollment.objects.get_or_create(
                    student=student, year=year, defaults={"section": section}
                )
                if cree:
                    stats["inscriptions"] += 1

                for code, valeur in ligne["grades"].items():
                    curriculum = curricula[code]
                    if valeur is None:
                        defaults = {"value": None, "status": GradeStatus.ABSENT}
                        stats["absences"] += 1
                    else:
                        defaults = {
                            "value": Decimal(str(valeur)),
                            "status": GradeStatus.ENTERED,
                        }
                        stats["notes"] += 1
                    Grade.objects.update_or_create(
                        enrollment=enrollment, curriculum=curriculum, defaults=defaults
                    )

            recompute_semester(fasl1, section)

        return stats

    def _rapport(self, stats: dict, conflits: dict, provisoire: bool) -> None:
        self.stdout.write(self.style.SUCCESS("\nImport termine."))
        for cle, valeur in stats.items():
            self.stdout.write(f"   {cle:<14} : {valeur}")
        if conflits and not provisoire:
            self.stdout.write(
                self.style.ERROR(
                    f"\n{stats['refusees']} etudiante(s) non importee(s) pour cause de "
                    "matricule en conflit. La direction doit leur attribuer un "
                    "matricule, ou relancer avec --provisional-matricules."
                )
            )
