#!/bin/bash
set -e

# ====== CONFIG ======
BASE="/var/www/pro"
RELEASES="$BASE/releases"
CURRENT="$BASE/back/current"
SHARED="$BASE/back_shared"
SERVICE="gunicorn_pro_back"
LOG="$SHARED/deploy.log"

# ====== LOCK ======
LOCK="/tmp/deploy.lock"
if [ -f "$LOCK" ]; then
  echo "🚫 Operação já em execução"
  exit 1
fi
trap "rm -f $LOCK" EXIT
touch "$LOCK"

# ====== LISTAR RELEASES ======
echo "📜 Releases disponíveis:"
cd "$RELEASES"
RELEASES_LIST=( $(ls -dt */) )

if [ ${#RELEASES_LIST[@]} -lt 2 ]; then
  echo "⚠️ Não há releases suficientes para rollback"
  exit 1
fi

# ====== ESCOLHER RELEASE ======
echo
echo "Quer escolher a release para rollback? (s/n)"
read -r CHOICE

if [[ "$CHOICE" =~ ^[Ss]$ ]]; then
    echo "Digite o número da release desejada:"
    for i in "${!RELEASES_LIST[@]}"; do
        echo "[$i] ${RELEASES_LIST[$i]%/}"
    done
    read -r SEL
    if [[ -z "${RELEASES_LIST[$SEL]}" ]]; then
        echo "❌ Opção inválida"
        exit 1
    fi
    TARGET_RELEASE="${RELEASES_LIST[$SEL]%/}"
else
    # Padrão: volta para a release anterior
    CURRENT_RELEASE=$(readlink -f "$CURRENT")
    for i in "${!RELEASES_LIST[@]}"; do
        FULL_PATH="$RELEASES/${RELEASES_LIST[$i]%/}"
        if [[ "$FULL_PATH" == "$CURRENT_RELEASE" ]]; then
            # Anterior é a próxima na lista
            TARGET_RELEASE="${RELEASES_LIST[$((i+1))]%/}"
            break
        fi
    done
    if [ -z "$TARGET_RELEASE" ]; then
        echo "❌ Não foi possível determinar release anterior"
        exit 1
    fi
fi

echo "🔄 Fazendo rollback para: $TARGET_RELEASE"
ln -sfn "$RELEASES/$TARGET_RELEASE" "$CURRENT"

# ====== RESTART SERVIÇO ======
echo "⚙️ Reiniciando serviço..."
systemctl restart "$SERVICE" 2>&1 | tee -a "$LOG"

echo "✅ Rollback concluído: $TARGET_RELEASE" | tee -a "$LOG"