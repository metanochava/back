SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

PY := python3
PIP := $(PY) -m pip
MANAGE := $(PY) manage.py
PYPROJECT := pyproject.toml
BACKUP_DIR := backups

# Comandos Django expostos diretamente pelo Makefile.
AUTH_COMMANDS := changepassword
AUTHTOKEN_COMMANDS := drf_create_token
CONTENTTYPES_COMMANDS := remove_stale_contenttypes
DJANGO_COMMANDS := \
	compilemessages createcachetable dbshell diffsettings dumpdata flush \
	inspectdb loaddata makemessages makemigrations optimizemigration \
	sendtestemail shell showmigrations sqlflush sqlmigrate \
	sqlsequencereset squashmigrations startapp startproject test testserver
DJANGO_RESAAS_COMMANDS := setup
REST_FRAMEWORK_COMMANDS := generateschema
SESSIONS_COMMANDS := clearsessions
STATICFILES_COMMANDS := collectstatic findstatic runserver

MANAGE_COMMANDS := \
	$(AUTH_COMMANDS) \
	$(AUTHTOKEN_COMMANDS) \
	$(CONTENTTYPES_COMMANDS) \
	$(DJANGO_COMMANDS) \
	$(DJANGO_RESAAS_COMMANDS) \
	$(REST_FRAMEWORK_COMMANDS) \
	$(SESSIONS_COMMANDS) \
	$(STATICFILES_COMMANDS)


# =========================================================
# VERSÃO
# =========================================================

define GET_VERSION
$(PY) -c "import tomli; print(tomli.load(open('$(PYPROJECT)', 'rb'))['project']['version'])"
endef


# =========================================================
# PHONY
# =========================================================

.PHONY: \
	dbbackup dbrestore dbbackups \
	help clean clean-migrations version status \
	gitsaas pipsaas libs reload \
	gitback gitrmc pull push \
	check migrations migrate createsuperuser \
	createuser create_root create_entity \
	sync_actions sync_language \
	dev pro staticfiles \
	teste teste1 teste2 \
	dbreset dbreset-migrate \
	bump_patch bump_minor bump_major \
	build upload \
	flow_init \
	features featuref \
	releases releasef \
	hotfixs hotfixf \
	env denv django \
	kill \
	$(MANAGE_COMMANDS)


# =========================================================
# AJUDA
# =========================================================

help:
	@echo "Comandos disponíveis:"
	@echo ""
	@echo "DJANGO"
	@echo "  make check                    - Verificar o projecto Django"
	@echo "  make migrations               - Criar migrations"
	@echo "  make migrate                  - Executar migrations"
	@echo "  make clean-migrations         - Eliminar migrations preservando __init__.py"
	@echo "  make createsuperuser          - Criar superutilizador"
	@echo "  make createuser               - Criar utilizador"
	@echo "  make create_root              - Criar utilizador/root inicial"
	@echo "  make create_entity            - Criar entidade"
	@echo "  make sync_actions             - Sincronizar actions"
	@echo "  make sync_language            - Sincronizar idiomas"
	@echo "  make staticfiles              - Executar collectstatic"
	@echo "  make django                   - Mostrar ajuda do manage.py"
	@echo ""
	@echo "SERVIDOR"
	@echo "  make dev                      - Runserver em 0.0.0.0:7001"
	@echo "  make pro                      - Runserver em 0.0.0.0:7000"
	@echo "  make reload                   - Reiniciar gunicorn_pro_back"
	@echo "  make kill                     - Terminar processo numa porta"
	@echo ""
	@echo "DEPENDÊNCIAS"
	@echo "  make gitsaas                  - Reinstalar django_resaas do GitHub/main"
	@echo "  make pipsaas                  - Actualizar django_resaas pelo PyPI"
	@echo "  make libs                     - Instalar requirements.txt"
	@echo ""
	@echo "BASE DE DADOS"
	@echo "  make dbreset                  - Eliminar todas as tabelas PostgreSQL"
	@echo "  make dbreset-migrate          - Limpar BD, migrar e criar root"
	@echo "  make dbbackup                 - Criar backup PostgreSQL"
	@echo "  make dbrestore                - Restaurar backup PostgreSQL"
	@echo "  make dbbackups                - Listar backups existentes"
	@echo ""
	@echo "GIT"
	@echo "  make status                   - Mostrar estado do Git"
	@echo "  make pull                     - Executar git pull"
	@echo "  make push                     - Enviar main e develop"
	@echo "  make gitback                  - Recuar último commit mantendo alterações"
	@echo "  make gitrmc                   - Remover ficheiro/pasta do tracking Git"
	@echo ""
	@echo "GIT FLOW"
	@echo "  make flow_init                - Inicializar Git Flow"
	@echo "  make features                 - Iniciar feature"
	@echo "  make featuref                 - Finalizar feature"
	@echo "  make releases                 - Iniciar release"
	@echo "  make releasef                 - Finalizar release"
	@echo "  make hotfixs                  - Iniciar hotfix"
	@echo "  make hotfixf                  - Finalizar hotfix"
	@echo ""
	@echo "VERSÃO / PACOTE"
	@echo "  make version                  - Mostrar versão actual"
	@echo "  make bump_patch               - Incrementar versão patch"
	@echo "  make bump_minor               - Incrementar versão minor"
	@echo "  make bump_major               - Incrementar versão major"
	@echo "  make build                    - Construir pacote"
	@echo "  make upload                   - Publicar pacote no PyPI"
	@echo ""
	@echo "AMBIENTE / LIMPEZA"
	@echo "  make env                      - Mostrar comando para activar venv"
	@echo "  make denv                     - Mostrar comando para sair da venv"
	@echo "  make clean                    - Limpar cache Python"
	@echo ""
	@echo "COMANDOS DJANGO DIRECTOS"
	@echo "  make <comando>                - Executar comando Django suportado"
	@echo "  make <comando> ARGS=\"...\"   - Executar comando Django com argumentos"

# =========================================================
# DEPENDÊNCIAS
# =========================================================

gitsaas:
	$(PIP) install \
		--no-cache-dir \
		--force-reinstall \
		git+https://github.com/metanochava/django_resaas.git@main

pipsaas:
	$(PIP) install --upgrade django_resaas

libs:
	$(PIP) install -r requirements.txt



# =========================================================
# SERVIÇO
# =========================================================

reload:
	systemctl daemon-reload
	systemctl restart gunicorn_pro_back
	systemctl status gunicorn_pro_back --no-pager


# =========================================================
# HELPERS
# =========================================================

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	@echo "Cache Python removida."


# =========================================================
# LIMPAR MIGRATIONS
# =========================================================

clean-migrations:
	@echo ""
	@echo "========================================================="
	@echo " ATENÇÃO: LIMPEZA DE MIGRATIONS"
	@echo "========================================================="
	@echo ""
	@echo "Serão eliminados:"
	@echo "  - */migrations/*.py"
	@echo "  - excepto */migrations/__init__.py"
	@echo "  - */migrations/*.pyc"
	@echo "  - */migrations/__pycache__/"
	@echo ""
	@echo "A base de dados NÃO será alterada."
	@echo ""

	read -p "Deseja continuar? Digite 'yes': " resposta

	if [[ "$$resposta" != "yes" ]]; then
		echo ""
		echo "Operação cancelada."
		exit 0
	fi

	echo ""
	echo "A remover migrations..."

	find . \
		-type f \
		-path "*/migrations/*.py" \
		! -name "__init__.py" \
		-print \
		-delete

	find . \
		-type f \
		-path "*/migrations/*.pyc" \
		-print \
		-delete

	find . \
		-type d \
		-path "*/migrations/__pycache__" \
		-prune \
		-print \
		-exec rm -rf {} +

	echo ""
	echo "========================================================="
	echo " Migrations removidas com sucesso."
	echo " __init__.py foi preservado em todas as apps."
	echo "========================================================="
	echo ""


version:
	@$(call GET_VERSION)

status:
	git status -sb


# =========================================================
# DJANGO
# =========================================================

check:
	$(MANAGE) check

migrations:
	$(MANAGE) makemigrations

migrate:
	$(MANAGE) migrate

createsuperuser:
	$(MANAGE) createsuperuser

createuser:
	$(MANAGE) createuser

create_root:
	$(MANAGE) create_root

create_entity:
	$(MANAGE) create_entity

sync_actions:
	$(MANAGE) sync_actions

sync_language:
	$(MANAGE) sync_language


# Encaminha os restantes alvos directamente para manage.py.
# Exemplo:
# make startapp ARGS=clientes

$(MANAGE_COMMANDS):
	$(MANAGE) $@ $(ARGS)


# =========================================================
# SERVIDOR DJANGO
# =========================================================

dev:
	$(MANAGE) runserver 0.0.0.0:7001

pro:
	$(MANAGE) runserver 0.0.0.0:7000

staticfiles:
	$(MANAGE) collectstatic --noinput


# =========================================================
# TESTES DE DEPENDÊNCIAS DO MAKE
# =========================================================

teste1:
	@echo "A apagar a base de dados...1"

teste2:
	@echo "A apagar a base de dados...2"

teste: teste1 teste2
	@echo "Teste concluído."


# =========================================================
# BASE DE DADOS POSTGRESQL
# =========================================================

dbreset:
	@echo ""
	@echo "========================================================="
	@echo " ATENÇÃO: RESET DA BASE DE DADOS"
	@echo "========================================================="
	@echo ""
	@echo "Todas as tabelas e dados serão eliminados."
	@echo ""

	read -p "Deseja continuar? Digite 'yes': " resposta

	if [[ "$$resposta" != "yes" ]]; then
		echo "Operação cancelada."
		exit 0
	fi

	echo ""
	echo "A apagar a base de dados..."

	echo "\
	DROP SCHEMA public CASCADE; \
	CREATE SCHEMA public; \
	GRANT ALL ON SCHEMA public TO public; \
	" | $(MANAGE) dbshell

	echo ""
	echo "Base de dados limpa."


dbreset-migrate: dbreset
	@echo ""
	@echo "A executar migrations..."
	$(MANAGE) migrate

	@echo ""
	@echo "Base de dados reconstruída."

	$(MANAGE) create_root

	@echo ""
	@echo "Basic settings done."


# =========================================================
# AJUDA DJANGO
# =========================================================

django:
	@echo ""
	$(MANAGE) -h


# =========================================================
# GIT BÁSICO
# =========================================================

pull:
	git pull

push:
	git push origin main develop

gitback:
	git reset --soft HEAD~1

gitrmc:
	read -p "Digite o caminho do ficheiro ou pasta: " caminho

	if [[ -z "$$caminho" ]]; then
		echo "Nenhum caminho fornecido."
		exit 1
	fi

	git rm --cached "$$caminho"


# =========================================================
# BUMP VERSION SEM COMMIT NEM TAG
# =========================================================

bump_patch:
	bump2version patch --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"
	echo "Nova versão: $$VERSION"

bump_minor:
	bump2version minor --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"
	echo "Nova versão: $$VERSION"

bump_major:
	bump2version major --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"
	echo "Nova versão: $$VERSION"


# =========================================================
# BUILD E UPLOAD PARA PYPI
# =========================================================

build:
	rm -rf build dist
	$(PY) -m build

upload:
	$(PY) -m twine upload dist/*


# =========================================================
# GIT FLOW
# =========================================================

flow_init:
	git flow init


# =========================================================
# FEATURE
# =========================================================

features:
	read -p "Nome da feature: " nome

	if [[ -z "$$nome" ]]; then
		echo "O nome da feature é obrigatório."
		exit 1
	fi

	git checkout develop
	git pull origin develop
	git flow feature start "$$nome"


featuref:
	read -p "Nome da feature: " nome

	if [[ -z "$$nome" ]]; then
		echo "O nome da feature é obrigatório."
		exit 1
	fi

	git flow feature finish "$$nome"
	git push origin develop


# =========================================================
# RELEASE
# =========================================================

releases:
	git checkout develop
	git pull origin develop

	read -p "Bump (patch/minor/major): " bump

	if [[ ! "$$bump" =~ ^(patch|minor|major)$$ ]]; then
		echo "Bump inválido. Use patch, minor ou major."
		exit 1
	fi

	bump2version "$$bump" --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"

	git add .
	git commit -m "bump version $$VERSION"
	git flow release start "$$VERSION"

	echo "Release $$VERSION iniciada."


releasef:
	VERSION="$$( $(call GET_VERSION) )"

	if ! git show-ref --verify --quiet \
		"refs/heads/release/$$VERSION"; then
		echo "A branch release/$$VERSION não existe."
		exit 1
	fi

	read -p "Mensagem do release v$$VERSION: " mensagem

	git flow release finish \
		-m "release: v$$VERSION - $$mensagem" \
		"$$VERSION"

	git push origin main develop --tags

	echo "Release $$VERSION finalizada."


# =========================================================
# HOTFIX
# =========================================================

hotfixs:
	read -p "Nome do hotfix: " nome

	if [[ -z "$$nome" ]]; then
		echo "O nome do hotfix é obrigatório."
		exit 1
	fi

	git checkout main
	git pull origin main
	git flow hotfix start "$$nome"


hotfixf:
	read -p "Nome do hotfix: " nome

	if [[ -z "$$nome" ]]; then
		echo "O nome do hotfix é obrigatório."
		exit 1
	fi

	git flow hotfix finish "$$nome"
	git push origin main develop --tags


# =========================================================
# AMBIENTE VIRTUAL
# =========================================================

env:
	@echo ""
	@echo "Execute o seguinte comando no terminal:"
	@echo "source /var/www/dev/back/venv/bin/activate"


denv:
	@echo ""
	@echo "Para sair do ambiente virtual execute:"
	@echo "deactivate"


# =========================================================
# BACKUP E RESTORE — POSTGRESQL
# =========================================================

dbbackup:
	@echo "A preparar backup da base de dados..."

	mkdir -p "$(BACKUP_DIR)"

	DB_NAME="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('NAME', ''))" \
	)"

	DB_USER="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('USER', ''))" \
	)"

	DB_PASSWORD="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('PASSWORD', ''))" \
	)"

	DB_HOST="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('HOST', ''))" \
	)"

	DB_PORT="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('PORT', ''))" \
	)"

	TIMESTAMP="$$(date +%Y%m%d_%H%M%S)"
	BACKUP_FILE="$(BACKUP_DIR)/$${DB_NAME}_$${TIMESTAMP}.dump"

	PG_ARGS=()

	if [[ -n "$$DB_HOST" ]]; then
		PG_ARGS+=(--host="$$DB_HOST")
	fi

	if [[ -n "$$DB_PORT" ]]; then
		PG_ARGS+=(--port="$$DB_PORT")
	fi

	if [[ -n "$$DB_USER" ]]; then
		PG_ARGS+=(--username="$$DB_USER")
	fi

	PGPASSWORD="$$DB_PASSWORD" pg_dump \
		"$${PG_ARGS[@]}" \
		--format=custom \
		--compress=9 \
		--no-owner \
		--no-privileges \
		--file="$$BACKUP_FILE" \
		"$$DB_NAME"

	echo ""
	echo "Backup criado com sucesso:"
	echo "$$BACKUP_FILE"


dbrestore:
	@echo "Backups disponíveis:"
	@echo ""

	mkdir -p "$(BACKUP_DIR)"

	ls -lh "$(BACKUP_DIR)"/*.dump 2>/dev/null || \
		echo "Nenhum backup encontrado."

	echo ""
	read -p "Caminho do backup: " BACKUP_FILE

	if [[ ! -f "$$BACKUP_FILE" ]]; then
		echo "O ficheiro não existe: $$BACKUP_FILE"
		exit 1
	fi

	echo ""
	echo "ATENÇÃO: os dados actuais serão substituídos."

	read -p "Digite 'yes' para continuar: " CONFIRMATION

	if [[ "$$CONFIRMATION" != "yes" ]]; then
		echo "Restore cancelado."
		exit 0
	fi

	DB_NAME="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('NAME', ''))" \
	)"

	DB_USER="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('USER', ''))" \
	)"

	DB_PASSWORD="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('PASSWORD', ''))" \
	)"

	DB_HOST="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('HOST', ''))" \
	)"

	DB_PORT="$$( $(MANAGE) shell -c \
		"from django.db import connection; print(connection.settings_dict.get('PORT', ''))" \
	)"

	PG_ARGS=()

	if [[ -n "$$DB_HOST" ]]; then
		PG_ARGS+=(--host="$$DB_HOST")
	fi

	if [[ -n "$$DB_PORT" ]]; then
		PG_ARGS+=(--port="$$DB_PORT")
	fi

	if [[ -n "$$DB_USER" ]]; then
		PG_ARGS+=(--username="$$DB_USER")
	fi

	echo "A restaurar a base de dados..."

	PGPASSWORD="$$DB_PASSWORD" pg_restore \
		"$${PG_ARGS[@]}" \
		--dbname="$$DB_NAME" \
		--clean \
		--if-exists \
		--no-owner \
		--no-privileges \
		--exit-on-error \
		"$$BACKUP_FILE"

	echo ""
	echo "Base de dados restaurada com sucesso."


dbbackups:
	@mkdir -p "$(BACKUP_DIR)"
	@echo "Backups disponíveis:"
	@ls -lh "$(BACKUP_DIR)"/*.dump 2>/dev/null || \
		echo "Nenhum backup encontrado."


# =========================================================
# PROCESSOS / PORTAS
# =========================================================

kill:
	@read -p "Port: " port; \
	pid=$$(sudo lsof -t -i:$$port); \
	if [ -n "$$pid" ]; then \
		echo "A terminar processo $$pid na porta $$port..."; \
		sudo kill -9 $$pid; \
	else \
		echo "Nenhum processo encontrado na porta $$port."; \
	fi