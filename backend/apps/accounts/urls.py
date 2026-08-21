from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.rbac_views import (
    DroitsUtilisateurView,
    MatriceDroitsView,
    UtilisateursDroitsView,
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
    path("rbac/matrice/", MatriceDroitsView.as_view(), name="rbac-matrice"),
    path("rbac/utilisateurs/", UtilisateursDroitsView.as_view(), name="rbac-utilisateurs"),
    path(
        "rbac/utilisateurs/<int:pk>/",
        DroitsUtilisateurView.as_view(),
        name="rbac-utilisateur",
    ),
    path("", include(router.urls)),
]
