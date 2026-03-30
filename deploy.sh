#!/bin/bash
set -e

# ====== CONFIG ======
BASE="/var/www/pro"
RELEASES="$BASE/releases"
CURRENT="$BASE/back/current"
SHARED="$BASE/back_shared"
REPO_URL="https://github.com/metanochava/back.git"
SERVICE="gunicorn_pro_back"
KEEP_RELEASES=5   # número de releases a manter

LOCK="/tmp/deploy.lock"
LOG="$SHARED/deploy.log"

TAG="$1"

if [ -z "$TAG" ]; then
  echo "❌ Precisas passar a TAG. Ex: ./deploy.sh v1.2.0"
  exit 1
fi

# ====== LOCK ======
if [ -f "$LOCK" ]; then
  echo "🚫 Deploy já em execução"
  exit 1
fi
trap "rm -f $LOCK" EXIT
touch "$LOCK"

TS=$(date +%Y%m%d%H%M%S)
NEW_RELEASE="$RELEASES/${TAG}-${TS}"

mkdir -p "$RELEASES" "$SHARED"
echo "🚀 Deploy TAG=$TAG -> $NEW_RELEASE"

# ====== CLONE ======
git clone --quiet "$REPO_URL" "$NEW_RELEASE"
cd "$NEW_RELEASE"

# ====== VALIDAR TAG ======
git fetch --tags
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "❌ Tag $TAG não existe no repositório"
  exit 1
fi

git checkout --quiet "$TAG"

# ====== VENV (AUTO-REPAIR) ======
VENV_DIR="$SHARED/venv"
VENV_PY="$VENV_DIR/bin/python"

echo "🐍 Verificando virtualenv..."

if [ ! -f "$VENV_PY" ] || ! "$VENV_PY" --version >/dev/null 2>&1; then
  echo "⚠️ Venv inválido. Recriando..."
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

PIP_CMD="$VENV_PY -m pip"

# ====== ENV ======
if [ -f "$SHARED/.env" ]; then
  set -a
  source "$SHARED/.env"
  set +a
fi

# ====== FIND manage.py ======
MANAGE_PATH=$(find "$NEW_RELEASE" -name manage.py | head -n 1)

if [ -z "$MANAGE_PATH" ]; then
  echo "❌ manage.py não encontrado"
  exit 1
fi

APP_DIR=$(dirname "$MANAGE_PATH")
cd "$APP_DIR"

# ====== INSTALL ======
echo "📦 Instalando dependências..."
$PIP_CMD install --upgrade pip 2>&1 | tee -a "$LOG"
$PIP_CMD install -r "$NEW_RELEASE/requirements.txt" 2>&1 | tee -a "$LOG"
$PIP_CMD install django_resaas 2>&1 | tee -a "$LOG"

# ====== DJANGO ======
echo "⚙️ Criando migrations..."
$VENV_PY manage.py makemigrations 2>&1 | tee -a "$LOG"
echo "⚙️ Rodando migrations..."
$VENV_PY manage.py migrate 2>&1 | tee -a "$LOG"

echo "📁 Collectstatic..."
$VENV_PY manage.py collectstatic --noinput 2>&1 | tee -a "$LOG"

# ====== MEDIA ======
mkdir -p "$SHARED/mediafiles"

# ====== SWITCH CURRENT ======
ln -sfn "$NEW_RELEASE" "$CURRENT"

# ====== RESTART ======
systemctl restart "$SERVICE" 2>&1 | tee -a "$LOG"

echo "✅ Deploy concluído: $TAG" | tee -a "$LOG"

# ====== LIMPAR RELEASES ANTIGOS ======
echo "🗑️ Limpando releases antigos, mantendo os últimos $KEEP_RELEASES..." | tee -a "$LOG"
cd "$RELEASES"
RELEASE_COUNT=$(ls -dt */ | wc -l)
if [ "$RELEASE_COUNT" -gt "$KEEP_RELEASES" ]; then
    TO_DELETE=$(ls -dt */ | tail -n +$((KEEP_RELEASES+1)))
    for d in $TO_DELETE; do
        echo "🗑️ Removendo release antigo: $d" | tee -a "$LOG"
        rm -rf "$d"
    done
fi