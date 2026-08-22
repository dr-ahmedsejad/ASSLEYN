#!/bin/sh
# ═══════════════════════════════════════════════════════════════════
# Demarrage du backend en conteneur.
#
# Les migrations passent avant gunicorn : le conteneur ne doit jamais servir
# une requete sur un schema en retard. Si elles echouent, `set -e` arrete
# tout — un demarrage refuse vaut mieux qu'une base a moitie migree.
#
# Aucune donnee n'est semee ici. L'import du fichier source est une decision
# humaine, pas un effet de bord du demarrage.
# ═══════════════════════════════════════════════════════════════════
set -eu

echo "▶ Migrations"
python manage.py migrate --noinput

echo "▶ Fichiers statiques"
python manage.py collectstatic --noinput --clear

# --workers : 3 suffit pour un institut de cette taille. La consultation des
# resultats est une pointe courte et tres cachee, pas une charge continue.
echo "▶ gunicorn sur 0.0.0.0:8010"
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:8010" \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile - \
  --capture-output
