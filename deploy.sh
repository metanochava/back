#!/bin/bash
set -e

# ====== CONFIG ======
BASE="/var/www/pro"
RELEASES="$BASE/releases"
CURRENT="$BASE/back/current"
PREVIOUS="$BASE/back/previous"
SHARED="$BASE/back_shared"
REPO_URL="https://github.com/metanochava/back.git"
SERVICE="gunicorn_pro_back"
KEEP_RELEASES=5

LOCK="/tmp/deploy.lock"
LOG="$SHARED/deploy.log"

TAG="$1"

if [ -z "$TAG" ]; then
  echo "❌ Precisas passar a TAG. Ex: ./deploy.sh v1.0.0"
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

git fetch --tags
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "❌ Tag $TAG não existe"
  exit 1
fi

git checkout --quiet "$TAG"

# ====== VENV (AUTO-REPAIR REAL) ======
VENV_DIR="$SHARED/venv"
VENV_PY="$VENV_DIR/bin/python"

echo "🐍 Verificando virtualenv..."

if [ ! -f "$VENV_PY" ] || ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
  echo "⚠️ Venv inválido. Recriando..."
  rm -rf "$VENV_DIR"

  python3 -m venv "$VENV_DIR"

  # 🔥 garantir pip
  "$VENV_DIR/bin/python" -m ensurepip --upgrade
fi

PIP="$VENV_PY -m pip"

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
$PIP install --upgrade pip 2>&1 | tee -a "$LOG"
$PIP install -r "$NEW_RELEASE/requirements.txt" 2>&1 | tee -a "$LOG"
$PIP install -U django_resaas 2>&1 | tee -a "$LOG"

# garantir gunicorn
$PIP install gunicorn 2>&1 | tee -a "$LOG"

# ====== VALIDAR DJANGO ======
echo "🧪 Validando Django..."
if ! $VENV_PY -c "import django" >/dev/null 2>&1; then
  echo "❌ Django não instalado corretamente"
  exit 1
fi

# ====== STATIC SHARED ======
mkdir -p "$SHARED/staticfiles"
ln -sfn "$SHARED/staticfiles" "$APP_DIR/staticfiles"

# ====== MEDIA ======
mkdir -p "$SHARED/mediafiles"

# ====== MIGRATE ======
echo "⚙️ Criando migrations..."
$VENV_PY manage.py makemigrations 2>&1 | tee -a "$LOG"

# ====== MIGRATE ======
echo "⚙️ Rodando migrations..."
$VENV_PY manage.py migrate 2>&1 | tee -a "$LOG"

# ====== COLLECTSTATIC ======
echo "📁 Collectstatic..."
$VENV_PY manage.py collectstatic --noinput 2>&1 | tee -a "$LOG"

# ====== BACKUP CURRENT ======
if [ -L "$CURRENT" ]; then
  PREV_TARGET=$(readlink "$CURRENT")
  ln -sfn "$PREV_TARGET" "$PREVIOUS"
fi

# ====== SWITCH ======
echo "🔄 Ativando nova release..."
ln -sfn "$NEW_RELEASE" "$CURRENT"

# ====== RESTART ======
echo "⚙️ Reiniciando serviço..."

if systemctl is-active --quiet "$SERVICE"; then
  systemctl reload "$SERVICE"
else
  echo "ℹ️ Serviço não estava ativo, iniciando..."
  systemctl start "$SERVICE"
fi

# 🔥 validar se subiu
sleep 2

if ! systemctl is-active --quiet "$SERVICE"; then
  echo "❌ Serviço falhou ao iniciar"
  journalctl -u "$SERVICE" -n 50
  exit 1
fi

echo "✅ Deploy concluído: $TAG" | tee -a "$LOG"

# ====== CLEAN OLD RELEASES ======
echo "🗑️ Limpando releases antigos..." | tee -a "$LOG"
cd "$RELEASES"

ls -dt */ | tail -n +$((KEEP_RELEASES+1)) | while read d; do
  echo "🗑️ Removendo $d" | tee -a "$LOG"
  rm -rf "$d"
done