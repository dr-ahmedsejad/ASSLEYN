from django.contrib import admin

from apps.grading.models import Grade, GradeHistory, GradingRule


@admin.register(GradingRule)
class GradingRuleAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "pass_threshold",
        "compensation_floor",
        "ranking_mode",
        "absence_policy",
        "is_active",
    ]
    list_filter = ["year", "is_active"]


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "curriculum", "value", "status", "updated_at"]
    list_filter = ["status", "curriculum__section", "curriculum__subject"]
    search_fields = ["enrollment__student__matricule"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(GradeHistory)
class GradeHistoryAdmin(admin.ModelAdmin):
    """Journal en lecture seule : une trace ne se corrige pas."""

    list_display = ["grade", "old_value", "new_value", "changed_by", "changed_at"]
    list_filter = ["changed_at"]
    readonly_fields = [f.name for f in GradeHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
