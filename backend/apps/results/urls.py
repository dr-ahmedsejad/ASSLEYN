from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.results.views import (
    AnnualResultViewSet,
    MyResultsView,
    RecomputeView,
    SemesterResultViewSet,
)

router = DefaultRouter()
router.register("semester-results", SemesterResultViewSet, basename="semester-result")
router.register("annual-results", AnnualResultViewSet, basename="annual-result")

urlpatterns = [
    path("results/me/", MyResultsView.as_view(), name="my-results"),
    path("results/recompute/", RecomputeView.as_view(), name="recompute"),
    path("", include(router.urls)),
]
