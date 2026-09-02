#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# ASSLEYN — sauvegarde complete du VPS, rapatriee sur le poste
#
#   bash telecharger-sauvegarde.sh root@203.0.113.10
#   bash telecharger-sauvegarde.sh root@203.0.113.10 /d/sauvegardes
#   bash telecharger-sauvegarde.sh root@203.0.113.10 --dernier
#
# Une seule commande, trois gestes : produire la sauvegarde sur le serveur,
# la descendre, et verifier ce qui est arrive.
#
# Pourquoi passer par `deploy.sh backup` plutot que de tirer un pg_dump
# directement dans un tube SSH : la sauvegarde reste aussi sur le serveur, ou
# la rotation garde les trente dernieres. Une copie unique, sur un seul poste,
# n'est pas une sauvegarde — c'est un deplacement.
#
# `--dernier` se contente de rapatrier la derniere sauvegarde existante, sans
# en produire une nouvelle. Utile juste apres un `deploy.sh backup` nocturne.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

CIBLE="${1:-}"
DESTINATION="${2:-$HOME/asleyn-sauvegardes}"
[ "$DESTINATION" = "--dernier" ] && DESTINATION="$HOME/asleyn-sauvegardes"

# Le dossier du depot sur le serveur, et celui des sauvegardes a cote —
# memes valeurs que deploy.sh.
RACINE_DISTANTE="${RACINE_DISTANTE:-/opt/asleyn}"
SAUVEGARDES_DISTANTES="${SAUVEGARDES_DISTANTES:-/opt/asleyn-backups}"

SANS_NOUVELLE=false
for argument in "$@"; do
  [ "$argument" = "--dernier" ] && SANS_NOUVELLE=true
done

log()  { printf '\033[1;32m▶ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠ %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

if [ -z "$CIBLE" ] || [ "$CIBLE" = "--dernier" ]; then
  err "Usage : bash telecharger-sauvegarde.sh utilisateur@adresse [dossier] [--dernier]"
fi

command -v ssh >/dev/null || err "ssh est introuvable sur ce poste."
command -v scp >/dev/null || err "scp est introuvable sur ce poste."

# ─── 1. Produire la sauvegarde sur le serveur ──────────────────────
if [ "$SANS_NOUVELLE" = true ]; then
  log "Aucune nouvelle sauvegarde demandee — on prend la derniere en date"
else
  log "Sauvegarde sur $CIBLE"
  # `deploy.sh backup` verifie deja le marqueur de fin et supprime le fichier
  # s'il est incomplet : un pg_dump interrompu produit un gzip valide mais
  # tronque, qu'aucun outil ne signale.
  ssh "$CIBLE" "cd '$RACINE_DISTANTE/deploy' && ./deploy.sh backup" \
    || err "La sauvegarde a echoue sur le serveur. Rien n'a ete telecharge."
fi

# ─── 2. Reperer le fichier le plus recent ──────────────────────────
DISTANT=$(ssh "$CIBLE" "ls -t '$SAUVEGARDES_DISTANTES'/asleyn_*.sql.gz 2>/dev/null | head -1")
[ -n "$DISTANT" ] || err "Aucune sauvegarde trouvee dans $SAUVEGARDES_DISTANTES."

NOM=$(basename "$DISTANT")
log "Fichier retenu : $NOM"

# ─── 3. Rapatrier ─────────────────────────────────────────────────
mkdir -p "$DESTINATION"
LOCAL="$DESTINATION/$NOM"

log "Telechargement vers $LOCAL"
scp "$CIBLE:$DISTANT" "$LOCAL" || err "Le telechargement a echoue."

# ─── 4. Verifier ce qui est arrive ────────────────────────────────
#
# Deux controles, parce qu'ils ne disent pas la meme chose : `gzip -t` atteste
# que l'archive n'a pas ete corrompue en chemin, le marqueur de fin atteste
# que le dump etait complet au depart.
gzip -t "$LOCAL" 2>/dev/null || err "Archive corrompue : $LOCAL"

if ! gunzip -c "$LOCAL" | tail -20 | grep -q "PostgreSQL database dump complete"; then
  err "Sauvegarde incomplete — le marqueur de fin est absent : $LOCAL"
fi

TAILLE=$(du -h "$LOCAL" | cut -f1)
LIGNES=$(gunzip -c "$LOCAL" | grep -c "^COPY " || true)

log "Sauvegarde verifiee"
printf '   fichier : %s\n' "$LOCAL"
printf '   taille  : %s\n' "$TAILLE"
printf '   tables  : %s bloc(s) de donnees\n' "$LIGNES"

# Ce fichier porte les dossiers nominatifs de 98 mineures : il merite des
# droits restreints, et n'a rien a faire dans un dossier synchronise en ligne.
chmod 600 "$LOCAL" 2>/dev/null || true
warn "Ce fichier contient des donnees personnelles. Gardez-le hors des dossiers synchronises."
