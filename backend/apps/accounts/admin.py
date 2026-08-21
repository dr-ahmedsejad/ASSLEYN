"""
Administration Django.

Ce back-office n'est pas l'interface de l'institut — celle-ci est en arabe,
cote Next.js. Il sert a l'exploitation technique : depannage, reprise de
donnees, verification d'un dossier.
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import Student, Teacher, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "full_name_ar", "role", "is_active", "must_change_password"]
    list_filter = ["role", "is_active", "must_change_password"]
    search_fields = ["username", "full_name_ar"]
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "المعهد",
            {"fields": ("full_name_ar", "role", "phone", "must_change_password")},
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("المعهد", {"fields": ("full_name_ar", "role")}),
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["matricule", "full_name_ar", "is_active", "user"]
    list_filter = ["is_active"]
    search_fields = ["matricule", "full_name_ar"]
    ordering = ["matricule"]
    autocomplete_fields = ["user"]


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ["full_name_ar", "phone", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["full_name_ar"]
