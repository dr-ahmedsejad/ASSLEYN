"""Reglages de developpement local."""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# En local le front tourne en HTTP : les cookies ne peuvent pas etre Secure.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

CORS_ALLOWED_ORIGINS = env(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"]
)
CSRF_TRUSTED_ORIGINS = env(
    "CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000"]
)

# Les taches s'executent en ligne : pas de Redis a lancer pour developper.
CELERY_TASK_ALWAYS_EAGER = True

# Le schema navigable est utile en developpement uniquement.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
