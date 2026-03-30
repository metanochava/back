#!/bin/bash
set -e

BASE="/var/www/pro"
RELEASES="$BASE/releases"
CURRENT="$BASE/back/current"
PREVIOUS="$BASE/back/previous"
SHARED="$BASE/back_shared"
SERVICE="gunicorn_pro_back"
LOG="$SHARED/deploy.log"

LOCK="/tmp/deploy.lock"

# LOCK
if [ -f "$LOCK" ]; then
  echo "🚫 Operação já em execução"
  exit 1
fi
trap "rm -f $LOCK" EXIT
touch "$LOCK"

cd "$RELEASES"

echo "📜 Releases disponíveis:"
RELEASES_LIST=( $(ls -dt */) )

if [ ${#RELEASES_LIST[@]} -lt 2 ]; then
  echo "⚠️ Não há releases suficientes para rollback"
  exit 1
fi

echo
read -p "Quer escolher a release? (s/n): " CHOICE

if [[ "$CHOICE" =~ ^[Ss]$ ]]; then
    for i in "${!RELEASES_LIST[@]}"; do
        echo "[$i] ${RELEASES_LIST[$i]%/}"
    done
    read -p "Escolha: " SEL

    TARGET_RELEASE="${RELEASES_LIST[$SEL]%/}"

    if [ -z "$TARGET_RELEASE" ]; then
        echo "❌ Opção inválida"
        exit 1
    fi
else
    CURRENT_RELEASE=$(readlink -f "$CURRENT")

    for i in "${!RELEASES_LIST[@]}"; do
        FULL="$RELEASES/${RELEASES_LIST[$i]%/}"
        if [[ "$FULL" == "$CURRENT_RELEASE" ]]; then
            TARGET_RELEASE="${RELEASES_LIST[$((i+1))]%/}"
            break
        fi
    done
fi

if [ -z "$TARGET_RELEASE" ]; then
  echo "❌ Não foi possível determinar release"
  exit 1
fi

TARGET_PATH="$RELEASES/$TARGET_RELEASE"

# VALIDAR EXISTÊNCIA
if [ ! -d "$TARGET_PATH" ]; then
  echo "❌ Release não existe: $TARGET_PATH"
  exit 1
fi

echo
echo "⚠️ Confirmar rollback para: $TARGET_RELEASE ? (s/n)"
read -r CONFIRM

if [[ ! "$CONFIRM" =~ ^[Ss]$ ]]; then
  echo "❌ Cancelado"
  exit 0
fi

# SALVAR CURRENT COMO PREVIOUS
if [ -L "$CURRENT" ]; then
  ln -sfn "$(readlink $CURRENT)" "$PREVIOUS"
fi

# SWITCH
echo "🔄 Aplicando rollback..."
ln -sfn "$TARGET_PATH" "$CURRENT"

# RESTART (GRACEFUL)
echo "⚙️ Recarregando serviço..."
systemctl reload "$SERVICE" || systemctl restart "$SERVICE"

echo "✅ Rollback concluído: $TARGET_RELEASE" | tee -a "$LOG"