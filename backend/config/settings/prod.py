"""
Reglages de production.

Ce module part du principe que l'application est servie derriere un reverse
proxy TLS. Toute valeur laissee vide fait echouer le demarrage : mieux vaut un
refus de demarrer qu'un deploiement silencieusement non securise.
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# --- Transport ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# --- Cookies ---
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# --- Sessions en cache pour tenir la charge de consultation des resultats ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/2"),
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# --- Journal d'audit sur fichier ---
LOGGING["handlers"]["audit_file"] = {  # noqa: F405
    "class": "logging.handlers.WatchedFileHandler",
    "filename": env("AUDIT_LOG_PATH", default="/var/log/asleyn/audit.log"),
    "formatter": "verbose",
}
LOGGING["loggers"]["asleyn.audit"]["handlers"] = ["audit_file", "console"]  # noqa: F405
