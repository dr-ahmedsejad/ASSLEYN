from django.contrib import admin

from apps.results.models import AnnualResult, SemesterResult, SubjectResult


class SubjectResultInline(admin.TabularInline):
    model = SubjectResult
    extra = 0
    readonly_fields = ["curriculum", "value", "effective_value", "coefficient", "decision"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SemesterResult)
class SemesterResultAdmin(admin.ModelAdmin):
    """
    Resultats calcules : consultation seulement.

    Les moyennes et les rangs ne se saisissent pas a la main — c'est
    precisement ce que le systeme remplace.
    """

    list_display = [
        "enrollment",
        "semester",
        "average",
        "rank",
        "decision_computed",
        "decision_final",
    ]
    list_filter = ["semester", "enrollment__section", "decision_final"]
    search_fields = ["enrollment__student__matricule"]
    inlines = [SubjectResultInline]
    readonly_fields = [
        "enrollment",
        "semester",
        "average",
        "total_weighted",
        "total_coefficient",
        "rank",
        "cohort_size",
        "decision_computed",
        "rule",
        "computed_at",
    ]

    def has_add_permission(self, request):
        return False


@admin.register(AnnualResult)
class AnnualResultAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "year", "average", "rank", "decision_final"]
    list_filter = ["year", "enrollment__section", "decision_final"]
    search_fields = ["enrollment__student__matricule"]

    def has_add_permission(self, request):
        return False
