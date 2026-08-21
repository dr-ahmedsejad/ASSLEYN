"""Tests de l'import de programme depuis un fichier JSON."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.core.management import CommandError, call_command

from apps.academics.models import Curriculum, SemesterState, Subject
from apps.grading.models import Grade, GradeStatus


def ecrire(tmp_path, contenu: dict):
    chemin = tmp_path / "programme.json"
    chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    return str(chemin)


@pytest.fixture
def programme(section_a, fasl2, subject_quran):
    return {
        "year": "2025-2026",
        "semester": 2,
        "subjects": [{"code": "SAWM", "name_ar": "الصوم"}],
        "programmes": [
            {
                "section": section_a.code,
                "matieres": [
                    {"subject": "QURAN", "coefficient": 5},
                    {"subject": "SAWM", "coefficient": 4},
                ],
            }
        ],
    }


@pytest.mark.django_db
class TestImport:
    def test_creation_des_matieres_et_du_programme(
        self, tmp_path, programme, section_a, fasl2
    ) -> None:
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

        assert Subject.objects.filter(code="SAWM").exists()
        lignes = Curriculum.objects.filter(section=section_a, semester=fasl2)
        assert lignes.count() == 2
        assert lignes.get(subject__code="QURAN").coefficient == Decimal("5")
        assert lignes.get(subject__code="SAWM").coefficient == Decimal("4")
        # L'ordre du fichier est conserve pour l'affichage.
        assert lignes.get(subject__code="QURAN").display_order == 0
        assert lignes.get(subject__code="SAWM").display_order == 1

    def test_dry_run_n_ecrit_rien(self, tmp_path, programme, fasl2) -> None:
        call_command(
            "importer_programme", ecrire(tmp_path, programme), "--dry-run", verbosity=0
        )
        assert Subject.objects.filter(code="SAWM").count() == 0
        assert Curriculum.objects.filter(semester=fasl2).count() == 0

    def test_idempotence(self, tmp_path, programme, fasl2) -> None:
        chemin = ecrire(tmp_path, programme)
        call_command("importer_programme", chemin, verbosity=0)
        call_command("importer_programme", chemin, verbosity=0)
        assert Curriculum.objects.filter(semester=fasl2).count() == 2
        assert Subject.objects.filter(code="SAWM").count() == 1

    def test_coefficient_mis_a_jour(
        self, tmp_path, programme, section_a, fasl2
    ) -> None:
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        programme["programmes"][0]["matieres"][0]["coefficient"] = 6
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

        assert Curriculum.objects.get(
            section=section_a, semester=fasl2, subject__code="QURAN"
        ).coefficient == Decimal("6")

    def test_matiere_retiree_est_desactivee_pas_supprimee(
        self, tmp_path, programme, section_a, fasl2
    ) -> None:
        """Une matière retirée peut déjà porter des notes : on la désactive."""
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        programme["programmes"][0]["matieres"] = [
            {"subject": "QURAN", "coefficient": 5}
        ]
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

        retiree = Curriculum.objects.get(
            section=section_a, semester=fasl2, subject__code="SAWM"
        )
        assert retiree.is_active is False

    def test_garder_absentes(self, tmp_path, programme, section_a, fasl2) -> None:
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        programme["programmes"][0]["matieres"] = [
            {"subject": "QURAN", "coefficient": 5}
        ]
        call_command(
            "importer_programme",
            ecrire(tmp_path, programme),
            "--garder-absentes",
            verbosity=0,
        )
        assert Curriculum.objects.get(
            section=section_a, semester=fasl2, subject__code="SAWM"
        ).is_active is True

    def test_reactivation(self, tmp_path, programme, section_a, fasl2) -> None:
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        Curriculum.objects.filter(subject__code="SAWM").update(is_active=False)
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        assert Curriculum.objects.get(subject__code="SAWM").is_active is True

    def test_les_notes_ne_sont_pas_touchees(
        self, tmp_path, programme, section_a, fasl2, enrollment, admin_user
    ) -> None:
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        matiere = Curriculum.objects.get(semester=fasl2, subject__code="SAWM")
        Grade.objects.create(
            enrollment=enrollment,
            curriculum=matiere,
            value=Decimal("14"),
            status=GradeStatus.ENTERED,
            entered_by=admin_user,
        )

        programme["programmes"][0]["matieres"] = [
            {"subject": "QURAN", "coefficient": 5}
        ]
        call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        assert Grade.objects.get(curriculum=matiere).value == Decimal("14")


@pytest.mark.django_db
class TestRefus:
    def test_annee_inconnue(self, tmp_path, programme) -> None:
        programme["year"] = "2099-2100"
        with pytest.raises(CommandError, match="Annee inconnue"):
            call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

    def test_fasl_inexistant(self, tmp_path, programme, fasl2) -> None:
        """L'annee existe, mais pas ce numero de فصل."""
        programme["semester"] = 3
        with pytest.raises(CommandError, match="introuvable"):
            call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

    def test_section_inconnue(self, tmp_path, programme, fasl2) -> None:
        programme["programmes"][0]["section"] = "INEXISTANTE"
        with pytest.raises(CommandError, match="erreur"):
            call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

    def test_matiere_absente_du_catalogue_et_du_fichier(
        self, tmp_path, programme, fasl2
    ) -> None:
        programme["subjects"] = []
        with pytest.raises(CommandError, match="erreur"):
            call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)
        assert Curriculum.objects.count() == 0

    def test_coefficient_negatif(self, tmp_path, programme, fasl2) -> None:
        programme["programmes"][0]["matieres"][0]["coefficient"] = -1
        with pytest.raises(CommandError, match="erreur"):
            call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

    def test_refus_si_fasl_publie(self, tmp_path, programme, fasl2) -> None:
        fasl2.state = SemesterState.PUBLISHED
        fasl2.save(update_fields=["state"])
        with pytest.raises(CommandError, match="publies"):
            call_command("importer_programme", ecrire(tmp_path, programme), verbosity=0)

    def test_fichier_introuvable(self, tmp_path) -> None:
        with pytest.raises(CommandError, match="introuvable"):
            call_command(
                "importer_programme", str(tmp_path / "absent.json"), verbosity=0
            )
