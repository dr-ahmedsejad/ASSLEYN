from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.grading.avancement import AvancementSaisieView
from apps.grading.views import (
    BulkGradeView,
    GradeHistoryViewSet,
    GradeSheetView,
    GradeViewSet,
    GradingRuleViewSet,
)

router = DefaultRouter()
router.register("grades", GradeViewSet, basename="grade")
router.register("grade-history", GradeHistoryViewSet, basename="grade-history")
router.register("grading-rules", GradingRuleViewSet, basename="grading-rule")

urlpatterns = [
    path(
        "grading/avancement/",
        AvancementSaisieView.as_view(),
        name="grade-avancement",
    ),
    path("grading/sheet/", GradeSheetView.as_view(), name="grade-sheet"),
    path("grading/sheet/bulk/", BulkGradeView.as_view(), name="grade-sheet-bulk"),
    path("", include(router.urls)),
]
