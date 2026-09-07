from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.competition.views import (
    CompetitionViewSet,
    DeciderTourView,
    EcranPublicView,
    LancerTourView,
)

router = DefaultRouter()
router.register("competitions", CompetitionViewSet, basename="competition")

urlpatterns = [
    path("tours/<int:pk>/lancer/", LancerTourView.as_view(), name="tour-lancer"),
    path("tours/<int:pk>/decider/", DeciderTourView.as_view(), name="tour-decider"),
    # Ouvert a tous : c'est l'ecran de la salle.
    path("direct/<str:code>/", EcranPublicView.as_view(), name="ecran-public"),
    path("", include(router.urls)),
]
