# ═══════════════════════════════════════════════════════════════════
# ASSLEYN — image du backend Django
#
# Aucune dependance ne se compile : psycopg, argon2-cffi et cryptography
# publient toutes des roues binaires. L'image reste donc sur `slim` sans
# gcc ni en-tetes de developpement — moins de paquets, moins de surface.
#
# Le conteneur tourne sous un compte sans privileges. Les volumes nommes
# (staticfiles, logs) heritent des droits du dossier tel qu'il existe dans
# l'image : d'ou le chown avant le USER.
# ═══════════════════════════════════════════════════════════════════
FROM python:3.12-slim-bookworm

# PYTHONUTF8 : les noms des etudiantes, des sections et des matieres sont en
# arabe. Sans lui, un simple print dans un journal casse le demarrage.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# Couche separee : les dependances ne sont reinstallees que si les fichiers
# requirements changent.
COPY requirements/ requirements/
RUN pip install --upgrade pip \
 && pip install -r requirements/base.txt \
 && pip install "gunicorn==23.0.0"

COPY . .

# Le compte applicatif est cree apres la copie pour que le chown ne porte que
# sur les dossiers reellement ecrits a l'execution.
RUN groupadd --system asleyn \
 && useradd --system --gid asleyn --home-dir /app --shell /usr/sbin/nologin asleyn \
 && mkdir -p /app/staticfiles /app/logs /app/media \
 && chown -R asleyn:asleyn /app/staticfiles /app/logs /app/media \
 && chmod +x /app/docker-entrypoint.sh

USER asleyn

EXPOSE 8010

# La sonde interroge la base : un Django qui a perdu PostgreSQL repond encore
# sur son port, mais ne sert plus a rien.
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=5 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/healthz/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
