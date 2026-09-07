"""Routage racine de l'API."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.health import healthz

urlpatterns = [
    # Sonde de l'orchestrateur, avant tout le reste : elle doit repondre meme
    # quand l'application est en peine.
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.academics.urls")),
    path("api/v1/", include("apps.grading.urls")),
    path("api/v1/", include("apps.results.urls")),
    path("api/v1/", include("apps.competition.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
    ]
