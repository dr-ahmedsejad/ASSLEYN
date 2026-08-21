#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# ASSLEYN — deploiement et exploitation
#
#   ./deploy.sh init            premier deploiement (secrets, build, demarrage)
#   ./deploy.sh update          mise a jour du code (git pull + reconstruction)
#   ./deploy.sh backup          sauvegarde SQL compressee
#   ./deploy.sh restore FICHIER restaure une sauvegarde (DESTRUCTIF)
#   ./deploy.sh reset-db        repart du dump initial (DESTRUCTIF)
#   ./deploy.sh setup-lan [IP]  certificat auto-signe pour un reseau local
#   ./deploy.sh manage ...      commande Django (migrate, createsuperuser…)
#   ./deploy.sh logs [service]  journaux
#   ./deploy.sh status          etat des conteneurs
#
# Les images sont construites ici, sur la machine de deploiement : aucun
# registre, aucune image publiee. `docker compose build` lit les Dockerfile
# des dossiers backend/ et frontend/ du depot.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$DEPLOY_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$REPO_DIR/../asleyn-backups}"

cd "$DEPLOY_DIR"

log()  { printf '\033[1;32m▶ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# Un mot de passe alphanumerique : il traverse une URL de connexion
# (postgres://user:mdp@db:5432/base) ou un caractere reserve se perdrait sans
# bruit. 32 caracteres d'alphabet reduit valent largement 24 caracteres
# d'alphabet complet.
secret() { LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "${1:-32}"; }

lire_env() {
  [ -f .env ] || err ".env absent — lancez d'abord : ./deploy.sh init"
  # shellcheck disable=SC1091
  set -a; . ./.env; set +a
}

attendre_sante() {
  local service="$1" limite="${2:-90}" ecoule=0
  log "Attente de $service"
  while [ "$ecoule" -lt "$limite" ]; do
    local etat
    etat=$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null \
           | awk -v s="$service" '$1 == s {print $2}')
    case "$etat" in
      healthy) log "$service est pret"; return 0 ;;
      unhealthy) docker compose logs "$service" --tail 40; err "$service en echec" ;;
    esac
    sleep 3; ecoule=$((ecoule + 3))
  done
  docker compose logs "$service" --tail 40
  err "$service n'est pas devenu sain en ${limite}s"
}

case "${1:-}" in

# ─── init ──────────────────────────────────────────────────────────
init)
  command -v docker >/dev/null || err "Docker n'est pas installe."
  docker compose version >/dev/null 2>&1 || err "Le plugin docker compose est absent."

  # Les dossiers montes doivent exister AVANT le premier demarrage : Docker
  # cree un repertoire a la place d'un chemin de montage manquant, ce qui
  # ferait echouer l'import du dump ou la lecture du certificat.
  mkdir -p initdb certs certbot-webroot "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR"

  if [ -f .env ]; then
    log ".env existant conserve"
  else
    read -rp "Domaine public ou adresse IP du serveur : " domaine
    [ -n "$domaine" ] || err "Un domaine est necessaire."
    log "Generation des secrets"
    umask 077
    cat > .env <<EOF
DOMAIN=$domaine
SECRET_KEY=$(secret 50)
DB_NAME=asleyn
DB_USER=asleyn
DB_PASSWORD=$(secret 32)
EOF
    warn "Secrets ecrits dans $DEPLOY_DIR/.env — sauvegardez-les hors de cette machine."
  fi
  lire_env

  if ls initdb/*.sql initdb/*.sql.gz >/dev/null 2>&1; then
    log "Dump present dans initdb/ : il sera importe au premier demarrage"
  else
    warn "initdb/ est vide : la base demarrera vierge, construite par les migrations."
    warn "Pour reprendre les donnees existantes, deposez-y un dump produit par :"
    warn "  pg_dump --no-owner --no-privileges asleyn | gzip > initdb/00-donnees.sql.gz"
  fi

  log "Construction des images (plusieurs minutes)"
  docker compose build

  log "Demarrage"
  docker compose up -d

  attendre_sante db 180
  attendre_sante backend 180
  attendre_sante frontend 120

  docker compose ps
  log "Deploiement termine — https://${DOMAIN}"
  [ "${ASLEYN_NGINX_CONF:-}" = "./nginx.lan.conf" ] \
    && warn "Certificat auto-signe : le navigateur affichera un avertissement, a accepter une fois."
  ;;

# ─── update ────────────────────────────────────────────────────────
update)
  lire_env
  log "Recuperation du code"
  git -C "$REPO_DIR" pull --ff-only

  log "Reconstruction des images applicatives"
  docker compose build backend frontend

  # Les migrations sont jouees par le point d'entree du conteneur, avant que
  # gunicorn n'accepte la premiere requete.
  log "Redemarrage"
  docker compose up -d backend frontend

  attendre_sante backend 180
  attendre_sante frontend 120
  docker compose ps
  ;;

# ─── backup ────────────────────────────────────────────────────────
backup)
  lire_env
  mkdir -p "$BACKUP_DIR"; chmod 700 "$BACKUP_DIR"
  horodatage=$(date +%Y%m%d_%H%M%S)
  fichier="$BACKUP_DIR/asleyn_$horodatage.sql.gz"

  log "Sauvegarde vers $fichier"
  # --no-owner --no-privileges : la sauvegarde doit pouvoir se restaurer dans
  # un conteneur neuf, ou les roles de celui-ci n'existent pas encore.
  # Le mot de passe passe par l'environnement, jamais par la ligne de commande
  # (visible de tout le systeme dans la liste des processus).
  docker compose exec -T -e PGPASSWORD="$DB_PASSWORD" db \
    pg_dump -U "$DB_USER" --no-owner --no-privileges --encoding=UTF8 "$DB_NAME" \
    | gzip > "$fichier"

  # Un pg_dump interrompu produit un fichier gzip valide mais tronque : on
  # verifie que le marqueur de fin est bien la. La fenetre est large : depuis
  # PostgreSQL 18, pg_dump ajoute des lignes \unrestrict apres ce marqueur.
  if ! gunzip -c "$fichier" | tail -20 | grep -q "PostgreSQL database dump complete"; then
    rm -f "$fichier"
    err "Sauvegarde incomplete — fichier supprime."
  fi

  chmod 600 "$fichier"
  log "Taille : $(du -h "$fichier" | cut -f1)"

  # Les 30 dernieres sont conservees. Ces fichiers portent les dossiers de
  # mineures : ils vivent avec des droits restreints et ne quittent pas la
  # machine sans chiffrement.
  ls -t "$BACKUP_DIR"/asleyn_*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm --
  log "Sauvegardes conservees : $(ls "$BACKUP_DIR"/asleyn_*.sql.gz 2>/dev/null | wc -l)"
  ;;

# ─── restore ───────────────────────────────────────────────────────
restore)
  lire_env
  fichier="${2:-}"
  [ -n "$fichier" ] || err "Usage : ./deploy.sh restore CHEMIN/vers/sauvegarde.sql.gz"
  [ -f "$fichier" ] || err "Fichier introuvable : $fichier"

  warn "Cette operation ECRASE le contenu actuel de la base $DB_NAME."
  read -rp "Tapez RESTAURER pour confirmer : " reponse
  [ "$reponse" = "RESTAURER" ] || err "Abandon."

  log "Sauvegarde de securite avant restauration"
  "$0" backup

  log "Arret du backend pendant la restauration"
  docker compose stop backend frontend

  log "Restauration de $fichier"
  gunzip -c "$fichier" | docker compose exec -T -e PGPASSWORD="$DB_PASSWORD" db \
    psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 --quiet

  log "Redemarrage"
  docker compose up -d backend frontend
  attendre_sante backend 180
  ;;

# ─── reset-db ──────────────────────────────────────────────────────
reset-db)
  lire_env
  warn "Cette operation SUPPRIME le volume de la base et repart du contenu de initdb/."
  warn "Toutes les notes saisies depuis le dernier import seront perdues."
  read -rp "Tapez REINITIALISER pour confirmer : " reponse
  [ "$reponse" = "REINITIALISER" ] || err "Abandon."

  log "Sauvegarde de securite avant destruction"
  "$0" backup || warn "Sauvegarde impossible (base deja arretee ?)"

  log "Arret et suppression des volumes"
  docker compose down -v

  log "Redemarrage — import du contenu de initdb/"
  docker compose up -d
  attendre_sante db 240
  attendre_sante backend 180
  ;;

# ─── setup-lan ─────────────────────────────────────────────────────
setup-lan)
  ip="${2:-}"
  [ -n "$ip" ] || err "Usage : ./deploy.sh setup-lan 192.168.1.50"

  mkdir -p certs
  if [ -f certs/selfsigned.crt ]; then
    warn "certs/selfsigned.crt existe deja — conserve. Supprimez-le pour regenerer."
  else
    log "Generation du certificat auto-signe pour $ip"
    # Le SAN sur l'IP est indispensable : depuis des annees, les navigateurs
    # ignorent le CN et n'acceptent qu'un nom present dans le SAN.
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
      -keyout certs/selfsigned.key \
      -out    certs/selfsigned.crt \
      -subj   "/CN=$ip" \
      -addext "subjectAltName=IP:$ip"
    chmod 600 certs/selfsigned.key
  fi

  log "Ajoutez ces deux lignes a $DEPLOY_DIR/.env :"
  echo "  DOMAIN=$ip"
  echo "  ASLEYN_NGINX_CONF=./nginx.lan.conf"
  log "Puis : ./deploy.sh init   (ou  docker compose up -d --build)"
  ;;

# ─── manage ────────────────────────────────────────────────────────
manage)
  shift
  [ $# -gt 0 ] || err "Usage : ./deploy.sh manage createsuperuser"
  docker compose exec backend python manage.py "$@"
  ;;

# ─── logs / status ─────────────────────────────────────────────────
logs)
  docker compose logs -f --tail 100 "${2:-}"
  ;;

status)
  docker compose ps
  echo
  log "Volumes"
  docker volume ls --filter name=deploy_ --filter name=asleyn
  echo
  log "Disque"
  df -h /var/lib/docker 2>/dev/null | tail -1 || true
  ;;

*)
  sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
  ;;
esac
