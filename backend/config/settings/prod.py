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
#
# `DJANGO_HTTPS` vaut vrai par defaut, et doit le rester : c'est le seul
# reglage qui empeche un mot de passe de circuler en clair.
#
# Le mettre a faux n'a qu'un usage legitime — un serveur joint par son adresse
# IP, sur lequel aucune autorite ne peut delivrer de certificat, et ou l'on
# accepte sciemment le risque. Dans ce cas les mots de passe et les cookies de
# session transitent en clair : quiconque se trouve sur le trajet peut les
# lire et se faire passer pour l'utilisateur. Un certificat auto-signe
# (deploy.sh setup-lan) supprime cette exposition pour une commande de plus.
HTTPS = env.bool("DJANGO_HTTPS", default=True)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = HTTPS
# HSTS ne se pose qu'en HTTPS. Le poser en clair serait au mieux ignore, au
# pire un piege : un navigateur qui l'aurait retenu refuserait ensuite toute
# connexion en clair, y compris apres un retour en arriere.
SECURE_HSTS_SECONDS = 31_536_000 if HTTPS else 0  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS
SECURE_HSTS_PRELOAD = HTTPS

# La sonde de l'orchestrateur interroge le conteneur en clair, de l'interieur :
# sans cette exemption, SECURE_SSL_REDIRECT lui repondrait 301 et Docker
# declarerait le service en panne.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]

# --- Cookies ---
#
# Un cookie marque `Secure` n'est simplement pas envoye sur une page en clair :
# le laisser vrai en HTTP ne protegerait rien et empecherait toute connexion —
# personne ne resterait authentifie.
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS

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
