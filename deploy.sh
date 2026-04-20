#!/bin/bash

echo "🚀 Deploy simples..."


cd /var/www/pro/back || exit

echo "📥 Atualizando código..."
git pull origin main

echo "🐍 Ativando venv..."
source ./venv/bin/activate

echo "📦 Instalando django_resaas..."
pip install -U django_resaas

echo "📦 Instalando dependências..."
pip install -r requirements.txt

echo "🧪 Verificando se há mudanças nos models..."

# 🔥 NÃO cria direto — só verifica primeiro
python3 manage.py makemigrations --check --dry-run
HAS_CHANGES=$?

if [ $HAS_CHANGES -ne 0 ]; then
  echo "⚠️ Models mudaram → criando migrations..."
  python3 manage.py makemigrations
else
  echo "✔ Sem mudanças nos models"
fi

echo "⚙️ Rodando migrations..."
python3 manage.py migrate --noinput

echo "📁 Collectstatic..."
python3 manage.py collectstatic --noinput

echo "🔄 Restart serviço..."
sudo systemctl restart gunicorn_pro_back

echo "✅ Deploy concluído!"