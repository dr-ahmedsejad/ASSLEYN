from django.contrib import admin

from apps.academics.models import (
    AcademicYear,
    Curriculum,
    Enrollment,
    Section,
    Semester,
    Subject,
    TeachingAssignment,
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ["label", "start_date", "end_date", "is_active"]
    list_filter = ["is_active"]


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ["__str__", "state", "weight", "start_date", "end_date"]
    list_filter = ["year", "state"]


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["name_ar", "code", "display_order", "is_active"]
    search_fields = ["name_ar", "code"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name_ar", "code", "display_order", "is_active"]
    search_fields = ["name_ar", "code"]


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    """Le programme : matiere x فصل x section, avec son coefficient."""

    list_display = ["section", "semester", "subject", "coefficient", "is_active"]
    list_filter = ["section", "semester", "subject", "is_active"]
    list_editable = ["coefficient"]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "section", "year", "is_active"]
    list_filter = ["section", "year", "is_active"]
    search_fields = ["student__matricule", "student__full_name_ar"]
    autocomplete_fields = ["student"]


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ["teacher", "curriculum", "is_active"]
    list_filter = ["is_active", "curriculum__section"]
