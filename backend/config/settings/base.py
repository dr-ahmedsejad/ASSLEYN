"""
Reglages communs a tous les environnements.

Regle de conception : aucune valeur sensible n'est ecrite ici. Tout secret
provient de l'environnement (fichier .env en developpement, variables
d'environnement en production).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "django_otp",
    "django_otp.plugins.otp_totp",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.academics",
    "apps.grading",
    "apps.results",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --------------------------------------------------------------------------
# Middleware
#
# L'ordre compte : CORS en tete, CSP en queue, AxesMiddleware apres
# l'authentification (il a besoin de request.user).
# --------------------------------------------------------------------------

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Base de donnees
# --------------------------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Authentification et mots de passe
# --------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

# Argon2id en tete : plus resistant que le PBKDF2 par defaut de Django.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Politique de mot de passe, telle que l'etablissement l'a fixee : huit
# caracteres au minimum, et un mot de passe entierement numerique est permis.
# Le mot de passe initial d'une etudiante est son matricule ecrit deux fois.
#
# Ce choix se defend ici, et pas partout. Huit chiffres, c'est cent millions
# de combinaisons : derisoire face a une machine qui essaie hors ligne, mais
# hors d'atteinte en ligne, ou le verrouillage progressif (apps/accounts/
# verrouillage.py) n'autorise que cinq essais avant de fermer la porte pour 5,
# puis 15, puis 30 minutes. C'est cette barriere-la qui tient, pas la longueur.
#
# Deux validateurs sont volontairement absents :
#   - NumericPasswordValidator refuserait les mots de passe numeriques ;
#   - UserAttributeSimilarityValidator refuserait un mot de passe derive du
#     nom d'utilisateur — ce qui est exactement la regle retenue.
# CommonPasswordValidator reste : il ne coute rien et ecarte « 12345678 »,
# la chaine la plus essayee au monde.
# Les messages sont les notres, pas ceux de Django : son catalogue arabe laisse
# le message de longueur en anglais, ce qui donnait « This password is too
# short » sur un ecran entierement arabe.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "apps.accounts.validators.LongueurMinimale",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "apps.accounts.validators.PasTropCourant"},
]

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

# Le verrouillage apres echecs repetes est traite par apps/accounts/
# verrouillage.py, et non plus par django-axes.
#
# Axes verrouille tres bien, mais a duree fixe. La regle de l'etablissement
# monte par paliers — 5 minutes, puis 15, puis 30 — et l'interface doit
# afficher un minuteur, lister les comptes fermes et permettre de les rouvrir.
# Tout cela se lit dans le journal des tentatives, qui devait de toute facon
# exister pour tracer les adresses IP. Deux comptabilites paralleles du meme
# phenomene auraient fini par se contredire ; il n'en reste qu'une.

# --------------------------------------------------------------------------
# Sessions (modele BFF : le navigateur ne detient jamais de jeton)
# --------------------------------------------------------------------------

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "asleyn_sid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 heures
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CSRF_COOKIE_HTTPONLY = False  # lu par le BFF Next.js pour reposter l'en-tete
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# --------------------------------------------------------------------------
# CORS : uniquement l'origine du front
# --------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# --------------------------------------------------------------------------
# Content-Security-Policy (django-csp 4.x)
# --------------------------------------------------------------------------

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'none'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'none'"],
        "form-action": ["'self'"],
    }
}

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Pagination maison : celle de DRF ignore `?page_size=`, que les ecrans
    # utilisent partout. Voir apps/common/pagination.py.
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.Pagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "600/hour",
        # Le debit de connexion est compte par adresse IP. L'institut est
        # derriere une seule sortie internet : dix connexions par heure
        # fermeraient la porte a toute une classe qui consulte ses resultats
        # le meme matin. Ce plafond n'est la que contre un automate ; c'est le
        # verrouillage par compte (apps/accounts/verrouillage.py) qui protege
        # un mot de passe, et lui ne se laisse pas diluer par le nombre.
        "login": "30/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Ma'had Al-Asleyn -- API",
    "DESCRIPTION": (
        "API de gestion pedagogique : structure annuelle, saisie des notes, "
        "calcul des moyennes, rangs et decisions."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# --------------------------------------------------------------------------
# Internationalisation : l'application est en arabe, RTL.
# --------------------------------------------------------------------------

LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "العربية")]
TIME_ZONE = "Africa/Nouakchott"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Fichiers statiques
# --------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    },
}

# --------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE

# --------------------------------------------------------------------------
# Journalisation
# --------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Journal dedie aux evenements sensibles : connexions, changements de
        # notes, publications. Destine a etre redirige vers un fichier scelle.
        "asleyn.audit": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
