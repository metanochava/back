#!/bin/bash
set -e

# ====== CONFIG ======
BASE="/var/www/pro"
RELEASES="$BASE/releases"
CURRENT="$BASE/back"
SHARED="$BASE/back_shared"
REPO_URL="https://github.com/metanochava/back.git"
SERVICE="gunicorn_pro_back"

LOCK="/tmp/deploy.lock"
LOG="/tmp/deploy.log"

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

# ====== CLONE ======
git clone --quiet "$REPO_URL" "$NEW_RELEASE"
cd "$NEW_RELEASE"

# ====== VALIDAR TAG ======
git fetch --tags
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "❌ Tag $TAG não existe no repositório" | tee -a "$LOG"
  exit 1
fi

git checkout --quiet "$TAG"

# ====== VENV (SEM activate) ======
VENV_PY="$SHARED/venv/bin/python3"
VENV_PIP="$SHARED/venv/bin/pip3"

# cria venv se não existir
if [ ! -f "$VENV_PY" ]; then
  echo "⚙️ Criando virtualenv..." | tee -a "$LOG"
  python3 -m venv "$SHARED/venv"
fi

# ====== ENV ======
if [ -f "$SHARED/.env" ]; then
  set -a
  source "$SHARED/.env"
  set +a
fi

# ====== FIND manage.py ======
MANAGE_PATH=$(find "$NEW_RELEASE" -name manage.py | head -n 1)

if [ -z "$MANAGE_PATH" ]; then
  echo "❌ manage.py não encontrado" | tee -a "$LOG"
  exit 1
fi

APP_DIR=$(dirname "$MANAGE_PATH")
cd "$APP_DIR"

# ====== INSTALL ======
$VENV_PIP install -r "$NEW_RELEASE/requirements.txt" >> "$LOG" 2>&1

# ====== DJANGO ======
$VENV_PY manage.py migrate >> "$LOG" 2>&1
$VENV_PY manage.py collectstatic --noinput >> "$LOG" 2>&1

# ====== MEDIA ======
mkdir -p "$SHARED/mediafiles"

# ====== SWITCH CURRENT ======
ln -sfn "$NEW_RELEASE" "$CURRENT"

# ====== RESTART ======
systemctl restart "$SERVICE"

echo "✅ Deploy concluído: $TAG" | tee -a "$LOG"