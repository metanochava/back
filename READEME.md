1) Backend Django com Gunicorn + systemd
1.1 Instalar deps
sudo apt update
sudo apt install -y python3-venv python3-pip nginx
1.2 Criar serviço systemd do Gunicorn
nano /etc/systemd/system/gunicorn_pro_back.servic

Cria e:
                                                                
[Unit]
Description=Gunicorn for Django (pro back)
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/dev/back

Environment="PATH=/var/www/pro/back/venv/bin"

ExecStart=/var/www/pro/back/venv/bin/gunicorn \
    saas.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 120

# 🔥 ADICIONA ISTO (importante)
RuntimeDirectory=gunicorn
RuntimeDirectoryMode=0755

[Install]
WantedBy=multi-user.target


Troca config.settings e config.wsgi pelo teu módulo real.

Ativa:

sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn_dev_back
sudo systemctl restart gunicorn_dev_back

sudo systemctl status gunicorn_dev_back --no-pager

● gunicorn_dev_back.service - Gunicorn for Django (dev back)
     Loaded: loaded (/etc/systemd/system/gunicorn_dev_back.service; enabled; vendor preset: enabled)
     Active: active (running) since Tue 2026-03-03 20:52:56 CET; 38s ago
   Main PID: 3573223 (gunicorn)
      Tasks: 5 (limit: 7017)
     Memory: 196.5M
        CPU: 15.564s
     CGroup: /system.slice/gunicorn_dev_back.service
             ├─3573223 /var/www/dev/back/venv/bin/python3 /var/www/dev/back/venv/bin/gunicorn saas.wsgi:application --bind 127.0.0.1:7001 --workers 3 --timeout 120
             ├─3573237 /var/www/dev/back/venv/bin/python3 /var/www/dev/back/venv/bin/gunicorn saas.wsgi:application --bind 127.0.0.1:7001 --workers 3 --timeout 120
             ├─3573238 /var/www/dev/back/venv/bin/python3 /var/www/dev/back/venv/bin/gunicorn saas.wsgi:application --bind 127.0.0.1:7001 --workers 3 --timeout 120
             └─3573239 /var/www/dev/back/venv/bin/python3 /var/www/dev/back/venv/bin/gunicorn saas.wsgi:application --bind 127.0.0.1:7001 --workers 3 --timeout 120


Logs:

sudo journalctl -u gunicorn_dev_back -f
2) Frontend Quasar em produção (build + Nginx)
2.1 Build

Dentro do frontend:

cd /var/www/front
npm ci
quasar build

O resultado fica em geral em:

/var/www/front/dist/spa

3) Nginx: servir Quasar + proxy para Django

Cria /etc/nginx/sites-available/clinica:

server {
    listen 80;
    server_name clinica.mytech.co.mz;

    # FRONT (Quasar build)
    root /var/www/front/dist/spa;
    index index.html;

    # SPA routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # BACKEND API (ajusta o prefixo conforme seu projeto)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Django admin (se quiser)
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # Static/Media (recomendado separar)
    location /static/ {
        alias /var/www/back/static/;
    }
    location /media/ {
        alias /var/www/back/media/;
    }
}

Ativar site:

sudo ln -s /etc/nginx/sites-available/clinica /etc/nginx/sites-enabled/clinica
sudo nginx -t
sudo systemctl restart nginx
4) HTTPS com Certbot (Let’s Encrypt)

Instala:

sudo apt install -y certbot python3-certbot-nginx

Gera SSL:

sudo certbot --nginx -d clinica.mytech.co.mz

Auto-renew já vem via timer; testa:

sudo certbot renew --dry-run
5) Django static/media (produção)

No settings.py:

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

Coletar:

cd /var/www/back
/var/www/back/venv/bin/python manage.py collectstatic --noinput

Migrações:

/var/www/back/venv/bin/python manage.py migrate
6) Deploy automático (script)

Cria /usr/local/bin/deploy_clinica.sh:

sudo nano /usr/local/bin/deploy_clinica.sh

Conteúdo:

#!/usr/bin/env bash
set -euo pipefail

BACK_DIR="/var/www/back"
FRONT_DIR="/var/www/front"

echo "==> Pull backend"
cd "$BACK_DIR"
git pull --rebase
"$BACK_DIR/venv/bin/pip" install -r requirements.txt
"$BACK_DIR/venv/bin/python" manage.py migrate
"$BACK_DIR/venv/bin/python" manage.py collectstatic --noinput

echo "==> Pull frontend"
cd "$FRONT_DIR"
git pull --rebase
npm ci
quasar build

echo "==> Restart services"
sudo systemctl restart gunicorn-back
sudo systemctl restart nginx

echo "DONE"

Permissões:

sudo chmod +x /usr/local/bin/deploy_clinica.sh
Rodar deploy manual
sudo /usr/local/bin/deploy_clinica.sh
7) Deploy automático “sozinho” (timer)

Cria /etc/systemd/system/deploy-clinica.service:

[Unit]
Description=Deploy Clinica

[Service]
Type=oneshot
ExecStart=/usr/local/bin/deploy_clinica.sh

Cria /etc/systemd/system/deploy-clinica.timer (ex: a cada 10 minutos):

[Unit]
Description=Run deploy-clinica periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target

Ativa:

sudo systemctl daemon-reload
sudo systemctl enable --now deploy-clinica.timer
sudo systemctl list-timers | grep deploy-clinica

Se preferir “deploy só quando fizer push”, dá pra fazer via webhook (GitHub Actions / webhook + token). Se quiser, eu te passo a versão webhook segura.

Checklist rápido de produção

✅ Nginx serve Quasar build (não quasar dev)

✅ Gunicorn em 127.0.0.1:8000 + systemd

✅ collectstatic + /static/ e /media/ no Nginx

✅ Certbot SSL funcionando

✅ Deploy script sem secrets no Git

✅ .env e chaves fora do repo

Se você me disser:

teu domínio final (prod) e se também vai ter *.dev.mytech.co.mz

o nome do teu módulo Django (ex: config.wsgi)

onde você quer /static e /media

…eu ajusto tudo com os nomes exatos (copiar/colar e já sobe).