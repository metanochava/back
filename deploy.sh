#!/usr/bin/env bash
#
# deploy.sh — provisiona uma VPS nova (Ubuntu/Debian) para correr este
# backend Django. Instala dependências de sistema, cria a venv, instala
# os pacotes Python (incluindo o framework django_resaas), prepara o
# .env, corre migrations/collectstatic e regista um serviço systemd
# para o Gunicorn.
#
# Uso:
#   1. git clone <repo> && cd <repo>
#   2. sudo ./deploy.sh
#
# Variáveis opcionais (podem ser exportadas antes de correr o script):
#   SERVICE_NAME     nome do serviço systemd   (default: gunicorn_<nome-da-pasta>)
#   GUNICORN_BIND     endereço:porta do Gunicorn (default: 127.0.0.1:8000)
#   GUNICORN_WORKERS  nº de workers             (default: 3)
#   GUNICORN_TIMEOUT  timeout em segundos       (default: 120)
#   RUN_USER          utilizador que corre o serviço (default: utilizador actual)
#
# Nginx/SSL não são configurados por este script — ver READEME.md.

set -euo pipefail
IFS=$'\n\t'

# --------------------------------------------------------------------
# Auto-detectar a pasta do projecto (onde este script está)
# --------------------------------------------------------------------

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/venv"

SERVICE_NAME="${SERVICE_NAME:-gunicorn_$(basename "$APP_DIR")}"
GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
RUN_USER="${RUN_USER:-$(id -un)}"
DJANGO_RESAAS_REF="${DJANGO_RESAAS_REF:-main}"

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

log()  { echo -e "\n\033[1;34m▶ $*\033[0m"; }
ok()   { echo -e "  \033[1;32m✔\033[0m $*"; }
warn() { echo -e "  \033[1;33m⚠\033[0m $*"; }
die()  { echo -e "  \033[1;31m✘ $*\033[0m" >&2; exit 1; }

trap 'die "Falhou na linha $LINENO. Nada foi feito depois desse ponto."' ERR

SUDO=""
if [[ "$EUID" -ne 0 ]]; then
    command -v sudo >/dev/null 2>&1 || die "É preciso root ou sudo para instalar pacotes de sistema."
    SUDO="sudo"
fi

[[ -f "$APP_DIR/manage.py" ]] || die "manage.py não encontrado em $APP_DIR — corre este script dentro do repo clonado."

log "Backend em: $APP_DIR"
log "Serviço systemd: $SERVICE_NAME  |  Gunicorn: $GUNICORN_BIND  |  utilizador: $RUN_USER"

# --------------------------------------------------------------------
# 1) Dependências de sistema
# --------------------------------------------------------------------

log "Instalando dependências de sistema (apt)..."

$SUDO apt-get update -y

$SUDO apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    build-essential \
    git \
    curl \
    postgresql-client \
    libpq-dev \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    fonts-dejavu-core

ok "Pacotes de sistema instalados (inclui libs do WeasyPrint para geração de PDF)."

# --------------------------------------------------------------------
# 2) Ambiente virtual Python
# --------------------------------------------------------------------

log "Preparando venv em $VENV_DIR ..."

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
    ok "venv criada."
else
    ok "venv já existia — reaproveitada."
fi

PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

"$PIP" install --upgrade pip setuptools wheel

# --------------------------------------------------------------------
# 3) Dependências Python
# --------------------------------------------------------------------

log "Instalando django_resaas (framework, via GitHub@${DJANGO_RESAAS_REF})..."
"$PIP" install --no-cache-dir --force-reinstall \
    "git+https://github.com/metanochava/django_resaas.git@${DJANGO_RESAAS_REF}"
ok "django_resaas instalado."

log "Instalando requirements.txt..."
"$PIP" install -r "$APP_DIR/requirements.txt"
ok "Dependências do projecto instaladas."

# --------------------------------------------------------------------
# 4) .env
# --------------------------------------------------------------------

log "Verificando .env..."

if [[ ! -f "$APP_DIR/.env" ]]; then
    warn ".env não existe — a criar um template em $APP_DIR/.env"
    cat > "$APP_DIR/.env" <<'ENV_TEMPLATE'
SERVER=CHANGE_ME
DEBUG=0
DEPLOY_TOKEN=CHANGE_ME
DJANGO_SAAS_CACHE_TIME=300
DJANGO_SAAS_REQUIRE_FRONT_END_CREDENTIALS=True
SECRET_KEY=CHANGE_ME
ALLOWED_HOSTS=CHANGE_ME
CSRF_TRUSTED_ORIGINS=CHANGE_ME
CORS_ALLOW_HEADERS=FEK,FEP,L,x-resaas-context
CORS_ALLOWED_ORIGINS=CHANGE_ME

SQL_ENGINE=postgresql
SQL_DATABASE=CHANGE_ME
SQL_USER=CHANGE_ME
SQL_PASSWORD=CHANGE_ME
SQL_HOST=CHANGE_ME
SQL_PORT=5432
CONNECTION_DB=POSTGRES

PROTOCOL=https
PORT=443
URL_FILE_KEY=CHANGE_ME
START_ADMIN_URL=admin
START_API_URL=api
MEDIA_URL=media
STATIC_URL=static
MEDIASTATIC_PATH=
AUTH_URL=auth
ALLOWED_URLS=rest,
TIME_ZONE=Africa/Maputo
TOKEN_KEY=CHANGE_ME
OTP_KEY=CHANGE_ME

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_USE_TLS=True
EMAIL_HOST=CHANGE_ME
EMAIL_HOST_USER=CHANGE_ME
EMAIL_HOST_PASSWORD=CHANGE_ME

TWILIO_ACCOUNT_SID=CHANGE_ME
TWILIO_AUTH_TOKEN=CHANGE_ME
WHATSAPP_BEARER=CHANGE_ME
ENV_TEMPLATE
    chmod 600 "$APP_DIR/.env"
    die "Preenche $APP_DIR/.env com os valores reais desta VPS e corre o script outra vez."
fi

ok ".env encontrado."

# --------------------------------------------------------------------
# 5) Django: check, migrate, collectstatic
# --------------------------------------------------------------------

mkdir -p "$APP_DIR/mediafiles" "$APP_DIR/staticfiles" "$APP_DIR/backups"

log "Django check..."
"$PY" "$APP_DIR/manage.py" check

log "Migrations..."
"$PY" "$APP_DIR/manage.py" migrate --noinput

log "Collectstatic..."
"$PY" "$APP_DIR/manage.py" collectstatic --noinput

ok "Base de dados migrada e estáticos recolhidos."

# --------------------------------------------------------------------
# 6) Serviço systemd do Gunicorn
# --------------------------------------------------------------------

log "Registando serviço systemd: $SERVICE_NAME"

$SUDO tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<UNIT
[Unit]
Description=Gunicorn for Django (${SERVICE_NAME})
After=network.target

[Service]
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${VENV_DIR}/bin/gunicorn \\
    saas.wsgi:application \\
    --bind ${GUNICORN_BIND} \\
    --workers ${GUNICORN_WORKERS} \\
    --timeout ${GUNICORN_TIMEOUT}

RuntimeDirectory=gunicorn
RuntimeDirectoryMode=0755
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now "$SERVICE_NAME"

ok "Serviço $SERVICE_NAME activo."

# --------------------------------------------------------------------
# Fim
# --------------------------------------------------------------------

echo
echo -e "\033[1;32m✅ Backend pronto nesta VPS.\033[0m"
echo "   Gunicorn a escutar em: $GUNICORN_BIND"
echo "   Ver logs:    sudo journalctl -u $SERVICE_NAME -f"
echo "   Ver estado:  sudo systemctl status $SERVICE_NAME --no-pager"
echo
echo "   Nginx + SSL não foram configurados por este script — segue o guia em READEME.md."
