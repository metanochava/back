#!/bin/bash
set -e

# ====== CONFIG ======
BASE="/var/www/pro"
RELEASES="$BASE/releases"
CURRENT="$BASE/back"
SERVICE="gunicorn_pro_back"
SHARED="$BASE/back_shared"
LOG="$SHARED/deploy.log"

# ====== OBTER RELEASES ======
cd "$RELEASES"
RELEASES_LIST=($(ls -dt */))  # mais recente primeiro

if [ ${#RELEASES_LIST[@]} -lt 2 ]; then
  echo "⚠️ Não há release anterior para rollback" | tee -a "$LOG"
  exit 1
fi

echo "📜 Releases disponíveis:"
for r in "${RELEASES_LIST[@]}"; do
    echo " - $r"
done

# ====== ROLLBACK ======
PREVIOUS_RELEASE="${RELEASES_LIST[1]}"  # segunda mais recente
echo "⏪ Fazendo rollback para $PREVIOUS_RELEASE" | tee -a "$LOG"

# Atualiza link simbólico
ln -sfn "$RELEASES/$PREVIOUS_RELEASE" "$CURRENT"

# Reinicia serviço
systemctl restart "$SERVICE"
echo "✅ Rollback concluído para $PREVIOUS_RELEASE" | tee -a "$LOG"