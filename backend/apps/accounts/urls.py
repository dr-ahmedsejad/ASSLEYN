from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.rbac_views import (
    ComptesView,
    DroitsUtilisateurView,
    MatriceDroitsView,
    UtilisateursDroitsView,
)
from apps.accounts.securite_views import (
    DeverrouillerView,
    JournalConnexionsView,
    ReinitialiserMotDePasseView,
    StatistiquesVisitesView,
    VerrousView,
)
from apps.accounts.views import (
    ChangePasswordView,
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    StudentViewSet,
    TeacherViewSet,
)

router = DefaultRouter()
router.register("students", StudentViewSet, basename="student")
router.register("teachers", TeacherViewSet, basename="teacher")

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path(
        "auth/change-password/",
        ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
    path(
        "securite/journal/",
        JournalConnexionsView.as_view(),
        name="securite-journal",
    ),
    path(
        "securite/statistiques/",
        StatistiquesVisitesView.as_view(),
        name="securite-statistiques",
    ),
    path("securite/verrous/", VerrousView.as_view(), name="securite-verrous"),
    path(
        "securite/verrous/<int:pk>/deverrouiller/",
        DeverrouillerView.as_view(),
        name="securite-deverrouiller",
    ),
    path(
        "securite/utilisateurs/<int:pk>/reinitialiser-mot-de-passe/",
        ReinitialiserMotDePasseView.as_view(),
        name="securite-reinitialiser",
    ),
    path("rbac/comptes/", ComptesView.as_view(), name="rbac-comptes"),
    path("rbac/matrice/", MatriceDroitsView.as_view(), name="rbac-matrice"),
    path("rbac/utilisateurs/", UtilisateursDroitsView.as_view(), name="rbac-utilisateurs"),
    path(
        "rbac/utilisateurs/<int:pk>/",
        DroitsUtilisateurView.as_view(),
        name="rbac-utilisateur",
    ),
    path("", include(router.urls)),
]
