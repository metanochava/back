#!/bin/bash
set -e

# ====== CONFIG ======
BASE="/var/www/pro"
RELEASES="$BASE/releases"
CURRENT="$BASE/back"              # symlink
SHARED="$BASE/back_shared"
REPO_URL="https://github.com/metanochava/back.git"
SERVICE="gunicorn_pro_back"

LOCK="/tmp/deploy.lock"
LOG="/tmp/deploy.log"

# TAG vem do argumento
TAG="$1"

if [ -z "$TAG" ]; then
  echo "❌ Precisas passar a TAG. Ex: ./deploy.sh v1.2.0" | tee -a "$LOG"
  exit 1
fi

# ====== LOCK ======
if [ -f "$LOCK" ]; then
  echo "🚫 Deploy já em execução" | tee -a "$LOG"
  exit 1
fi
trap "rm -f $LOCK" EXIT
touch "$LOCK"

TS=$(date +%Y%m%d%H%M%S)
NEW_RELEASE="$RELEASES/${TAG}-${TS}"

mkdir -p "$RELEASES" "$SHARED"
echo "🚀 Deploy TAG=$TAG -> $NEW_RELEASE" | tee -a "$LOG"

# ====== CLONE + CHECKOUT TAG ======
git clone --quiet "$REPO_URL" "$NEW_RELEASE"
cd "$NEW_RELEASE"
git checkout --quiet "$TAG"

# ====== VENV (shared) ======
# Assumindo venv em $SHARED/venv
source "$SHARED/venv/bin/activate"

# ====== ENV ======
# se usas .env
if [ -f "$SHARED/.env" ]; then
  set -a
  source "$SHARED/.env"
  set +a
fi

# ====== INSTALL + MIGRATE + STATIC ======
pip install -r requirements.txt >> "$LOG" 2>&1
python manage.py migrate >> "$LOG" 2>&1
python manage.py collectstatic --noinput >> "$LOG" 2>&1

# ====== MEDIA (shared) ======
# Se o projeto usa MEDIA_ROOT /var/www/back/mediafiles, ajusta para apontar pro shared:
# Exemplo: ln -sfn "$SHARED/mediafiles" "$NEW_RELEASE/mediafiles"
# (depende do teu settings.py)
mkdir -p "$SHARED/mediafiles"

# ====== SWITCH CURRENT ======
ln -sfn "$NEW_RELEASE" "$CURRENT"

# ====== RESTART ======
systemctl restart "$SERVICE"

echo "✅ Deploy concluído: $TAG" | tee -a "$LOG"