"""
Fixtures partagees par les tests.

Le decor est volontairement reduit : deux sections, deux matieres, trois
utilisateurs. Assez pour verifier que chacun voit ce qu'il doit voir, et rien
de plus.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    Section,
    Semester,
    SemesterState,
    Subject,
    TeachingAssignment,
)
from apps.accounts.models import Role, Student, Teacher, User
from apps.results.services import default_rule_for

MOT_DE_PASSE = "Un-Mot-De-Passe-Solide-2026"


@pytest.fixture
def year(db) -> AcademicYear:
    return AcademicYear.objects.create(
        label="2025-2026",
        start_date=date(2025, 10, 1),
        end_date=date(2026, 6, 30),
        is_active=True,
    )


@pytest.fixture
def rule(year: AcademicYear):
    return default_rule_for(year)


@pytest.fixture
def fasl1(year: AcademicYear) -> Semester:
    return Semester.objects.create(
        year=year,
        number=1,
        start_date=date(2025, 10, 1),
        end_date=date(2026, 1, 31),
        state=SemesterState.OPEN,
    )


@pytest.fixture
def fasl2(year: AcademicYear) -> Semester:
    return Semester.objects.create(
        year=year,
        number=2,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 6, 30),
        state=SemesterState.DRAFT,
    )


@pytest.fixture
def section_a(db) -> Section:
    return Section.objects.create(code="SEC-A", name_ar="المربيات")


@pytest.fixture
def section_b(db) -> Section:
    return Section.objects.create(code="SEC-B", name_ar="الحافظات")


@pytest.fixture
def subject_quran(db) -> Subject:
    return Subject.objects.create(code="QURAN", name_ar="القرآن الكريم")


@pytest.fixture
def subject_fiqh(db) -> Subject:
    return Subject.objects.create(code="FIQH", name_ar="الفقه")


@pytest.fixture
def curriculum_a_quran(section_a, fasl1, subject_quran) -> Curriculum:
    return Curriculum.objects.create(
        section=section_a, semester=fasl1, subject=subject_quran, coefficient=Decimal("5")
    )


@pytest.fixture
def curriculum_a_fiqh(section_a, fasl1, subject_fiqh) -> Curriculum:
    return Curriculum.objects.create(
        section=section_a, semester=fasl1, subject=subject_fiqh, coefficient=Decimal("3")
    )


@pytest.fixture
def curriculum_b_quran(section_b, fasl1, subject_quran) -> Curriculum:
    return Curriculum.objects.create(
        section=section_b, semester=fasl1, subject=subject_quran, coefficient=Decimal("5")
    )


def _user(username: str, role: str, nom: str) -> User:
    user = User.objects.create_user(
        username=username, password=MOT_DE_PASSE, full_name_ar=nom
    )
    user.role = role
    user.save(update_fields=["role"])
    return user


@pytest.fixture
def admin_user(db) -> User:
    return _user("admin", Role.ADMIN, "مدير المعهد")


@pytest.fixture
def teacher_user(db) -> User:
    return _user("prof", Role.TEACHER, "أستاذ القرآن")


@pytest.fixture
def teacher(teacher_user: User) -> Teacher:
    return Teacher.objects.create(user=teacher_user, full_name_ar=teacher_user.full_name_ar)


@pytest.fixture
def teacher_assigned(teacher: Teacher, curriculum_a_quran: Curriculum) -> Teacher:
    """Enseignant affecte a القرآن de la section A — et a rien d'autre."""
    TeachingAssignment.objects.create(teacher=teacher, curriculum=curriculum_a_quran)
    return teacher


@pytest.fixture
def student_user(db) -> User:
    return _user("24001", Role.STUDENT, "طالبة أولى")


@pytest.fixture
def student(student_user: User) -> Student:
    return Student.objects.create(
        user=student_user, matricule="24001", full_name_ar=student_user.full_name_ar
    )


@pytest.fixture
def enrollment(student: Student, section_a: Section, year: AcademicYear) -> Enrollment:
    return Enrollment.objects.create(student=student, section=section_a, year=year)


@pytest.fixture
def autre_enrollment(section_a: Section, year: AcademicYear) -> Enrollment:
    """Une camarade de la meme section, sans compte utilisateur."""
    autre = Student.objects.create(matricule="24002", full_name_ar="طالبة ثانية")
    return Enrollment.objects.create(student=autre, section=section_a, year=year)


@pytest.fixture
def enrollment_section_b(section_b: Section, year: AcademicYear) -> Enrollment:
    autre = Student.objects.create(matricule="24050", full_name_ar="طالبة من قسم آخر")
    return Enrollment.objects.create(student=autre, section=section_b, year=year)


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def api_admin(admin_user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(admin_user)
    return client


@pytest.fixture
def api_teacher(teacher_assigned: Teacher) -> APIClient:
    client = APIClient()
    client.force_authenticate(teacher_assigned.user)
    return client


@pytest.fixture
def api_student(student: Student) -> APIClient:
    client = APIClient()
    client.force_authenticate(student.user)
    return client
