SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

PY := python3
PIP := $(PY) -m pip
MANAGE := $(PY) manage.py
PYPROJECT := pyproject.toml
BACKUP_DIR := backups

# Django commands exposed directly by the Makefile.
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
# VERSION
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
# HELP
# =========================================================

help:
	@echo "Available commands:"
	@echo ""
	@echo "DJANGO"
	@echo "  make check                    - Check the Django project"
	@echo "  make migrations               - Create migrations"
	@echo "  make migrate                  - Apply migrations"
	@echo "  make clean-migrations         - Delete migrations while preserving __init__.py"
	@echo "  make createsuperuser          - Create a superuser"
	@echo "  make createuser               - Create a user"
	@echo "  make create_root              - Create the initial/root user"
	@echo "  make create_entity            - Create an entity"
	@echo "  make sync_actions             - Synchronize actions"
	@echo "  make sync_language            - Synchronize languages"
	@echo "  make staticfiles              - Run collectstatic"
	@echo "  make django                   - Show manage.py help"
	@echo ""
	@echo "SERVER"
	@echo "  make dev                      - Run server on 0.0.0.0:7001"
	@echo "  make pro                      - Run server on 0.0.0.0:7000"
	@echo "  make reload                   - Restart gunicorn_pro_back"
	@echo "  make kill                     - Terminate a process on a port"
	@echo ""
	@echo "DEPENDENCIES"
	@echo "  make gitsaas                  - Reinstall django_resaas from GitHub/main"
	@echo "  make pipsaas                  - Upgrade django_resaas from PyPI"
	@echo "  make libs                     - Install requirements.txt"
	@echo ""
	@echo "DATABASE"
	@echo "  make dbreset                  - Drop all PostgreSQL tables/data"
	@echo "  make dbreset-migrate          - Reset DB, migrate, and create root"
	@echo "  make dbbackup                 - Create a PostgreSQL backup"
	@echo "  make dbrestore                - Restore a PostgreSQL backup"
	@echo "  make dbbackups                - List existing backups"
	@echo ""
	@echo "GIT"
	@echo "  make status                   - Show Git status"
	@echo "  make pull                     - Run git pull"
	@echo "  make push                     - Push main and develop"
	@echo "  make gitback                  - Undo the last commit while keeping changes"
	@echo "  make gitrmc                   - Remove a file/directory from Git tracking"
	@echo ""
	@echo "GIT FLOW"
	@echo "  make flow_init                - Initialize Git Flow"
	@echo "  make features                 - Start a feature"
	@echo "  make featuref                 - Finish a feature"
	@echo "  make releases                 - Start a release"
	@echo "  make releasef                 - Finish a release"
	@echo "  make hotfixs                  - Start a hotfix"
	@echo "  make hotfixf                  - Finish a hotfix"
	@echo ""
	@echo "VERSION / PACKAGE"
	@echo "  make version                  - Show current version"
	@echo "  make bump_patch               - Increment patch version"
	@echo "  make bump_minor               - Increment minor version"
	@echo "  make bump_major               - Increment major version"
	@echo "  make build                    - Build the package"
	@echo "  make upload                   - Upload the package to PyPI"
	@echo ""
	@echo "ENVIRONMENT / CLEANUP"
	@echo "  make env                      - Show the command to activate the virtual environment"
	@echo "  make denv                     - Show the command to deactivate the virtual environment"
	@echo "  make clean                    - Clean Python cache files"
	@echo ""
	@echo "DIRECT DJANGO COMMANDS"
	@echo "  make <command>                - Run a supported Django command"
	@echo "  make <command> ARGS=\"...\"   - Run a Django command with arguments"

# =========================================================
# DEPENDENCIES
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
# SERVICE
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
	@echo "Python cache removed."


# =========================================================
# CLEAN MIGRATIONS
# =========================================================

clean-migrations:
	@echo ""
	@echo "========================================================="
	@echo " WARNING: MIGRATION CLEANUP"
	@echo "========================================================="
	@echo ""
	@echo "The following will be deleted:"
	@echo "  - */migrations/*.py"
	@echo "  - except */migrations/__init__.py"
	@echo "  - */migrations/*.pyc"
	@echo "  - */migrations/__pycache__/"
	@echo ""
	@echo "The database will NOT be modified."
	@echo ""

	read -p "Continue? Type 'yes': " resposta

	if [[ "$$resposta" != "yes" ]]; then
		echo ""
		echo "Operation cancelled."
		exit 0
	fi

	echo ""
	echo "Removing migrations..."

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
	echo " Migrations removed successfully."
	echo " __init__.py was preserved in all apps."
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


# Forward the remaining targets directly to manage.py.
# Example:
# make startapp ARGS=clientes

$(MANAGE_COMMANDS):
	$(MANAGE) $@ $(ARGS)


# =========================================================
# DJANGO SERVER
# =========================================================

dev:
	$(MANAGE) runserver 0.0.0.0:7001

pro:
	$(MANAGE) runserver 0.0.0.0:7000

staticfiles:
	$(MANAGE) collectstatic --noinput


# =========================================================
# MAKE DEPENDENCY TESTS
# =========================================================

teste1:
	@echo "Deleting the database...1"

teste2:
	@echo "Deleting the database...2"

teste: teste1 teste2
	@echo "Test completed."


# =========================================================
# POSTGRESQL DATABASE
# =========================================================

dbreset:
	@echo ""
	@echo "========================================================="
	@echo " WARNING: DATABASE RESET"
	@echo "========================================================="
	@echo ""
	@echo "All tables and data will be deleted."
	@echo ""

	read -p "Continue? Type 'yes': " resposta

	if [[ "$$resposta" != "yes" ]]; then
		echo "Operation cancelled."
		exit 0
	fi

	echo ""
	echo "Deleting the database..."

	echo "\
	DROP SCHEMA public CASCADE; \
	CREATE SCHEMA public; \
	GRANT ALL ON SCHEMA public TO public; \
	" | $(MANAGE) dbshell

	echo ""
	echo "Database cleared."


dbreset-migrate: dbreset
	@echo ""
	@echo "Applying migrations..."
	$(MANAGE) migrate

	@echo ""
	@echo "Database rebuilt."

	$(MANAGE) create_root

	@echo ""
	@echo "Basic settings done."


# =========================================================
# HELP DJANGO
# =========================================================

django:
	@echo ""
	$(MANAGE) -h


# =========================================================
# BASIC GIT
# =========================================================

pull:
	git pull

push:
	git push origin main develop

gitback:
	git reset --soft HEAD~1

gitrmc:
	read -p "Enter file or directory path: " caminho

	if [[ -z "$$caminho" ]]; then
		echo "No path provided."
		exit 1
	fi

	git rm --cached "$$caminho"


# =========================================================
# BUMP VERSION WITHOUT COMMIT OR TAG
# =========================================================

bump_patch:
	bump2version patch --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"
	echo "New version: $$VERSION"

bump_minor:
	bump2version minor --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"
	echo "New version: $$VERSION"

bump_major:
	bump2version major --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"
	echo "New version: $$VERSION"


# =========================================================
# BUILD AND UPLOAD TO PYPI
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
	read -p "Feature name: " nome

	if [[ -z "$$nome" ]]; then
		echo "Feature name is required."
		exit 1
	fi

	git checkout develop
	git pull origin develop
	git flow feature start "$$nome"


featuref:
	read -p "Feature name: " nome

	if [[ -z "$$nome" ]]; then
		echo "Feature name is required."
		exit 1
	fi

	git flow feature finish "$$nome"
	git push origin develop


# =========================================================
# RELEASE
# =========================================================

releases:
	if [[ -n "$$(git status --porcelain)" ]]; then
		echo "Working tree is not clean. Commit or stash your changes before starting a release."
		exit 1
	fi

	mapfile -t OPEN_RELEASES < <(git for-each-ref \
		--format='%(refname:short)' \
		'refs/heads/release/*' 2>/dev/null || true)

	if (( $${#OPEN_RELEASES[@]} > 0 )); then
		echo ""
		echo "Cannot start a new release."
		echo "The following release branch is still open:"
		printf '  %s\n' "$${OPEN_RELEASES[@]}"
		echo ""
		echo "Finish the active release with:"
		echo "  make releasef"
		echo ""
		echo "If the release is obsolete, inspect it before removing it:"
		echo "  git log develop..$${OPEN_RELEASES[0]} --oneline"
		echo "  git branch -D $${OPEN_RELEASES[0]}"
		echo ""
		exit 1
	fi

	git checkout develop
	git pull --ff-only origin develop

	read -p "Bump (patch/minor/major): " bump

	if [[ ! "$$bump" =~ ^(patch|minor|major)$$ ]]; then
		echo "Invalid bump. Use patch, minor, or major."
		exit 1
	fi

	CURRENT_VERSION="$$( $(call GET_VERSION) )"
	NEXT_VERSION="$$(CURRENT_VERSION="$$CURRENT_VERSION" BUMP="$$bump" $(PY) -c "import os; p=[int(x) for x in os.environ['CURRENT_VERSION'].split('.')]; b=os.environ['BUMP']; i={'major':0,'minor':1,'patch':2}[b]; p[i]+=1; p[i+1:]=[0]*(2-i); print('.'.join(map(str,p)))")"

	if git show-ref --verify --quiet "refs/heads/release/$$NEXT_VERSION" || \
	   git ls-remote --exit-code --heads origin "release/$$NEXT_VERSION" >/dev/null 2>&1; then
		echo "Release branch release/$$NEXT_VERSION already exists."
		exit 1
	fi

	if git rev-parse -q --verify "refs/tags/$$NEXT_VERSION" >/dev/null || \
	   git rev-parse -q --verify "refs/tags/v$$NEXT_VERSION" >/dev/null; then
		echo "A tag for version $$NEXT_VERSION already exists."
		exit 1
	fi

	git flow release start "$$NEXT_VERSION"
	bump2version "$$bump" --no-commit --no-tag
	VERSION="$$( $(call GET_VERSION) )"

	if [[ "$$VERSION" != "$$NEXT_VERSION" ]]; then
		echo "Version mismatch: expected $$NEXT_VERSION but pyproject.toml contains $$VERSION."
		exit 1
	fi

	git add .bumpversion.cfg "$(PYPROJECT)"
	git commit -m "bump version $$VERSION"

	echo "Release $$VERSION started on branch release/$$VERSION."


releasef:
	CURRENT_BRANCH="$$(git branch --show-current)"

	if [[ "$$CURRENT_BRANCH" == release/* ]]; then
		RELEASE_BRANCH="$$CURRENT_BRANCH"
	else
		mapfile -t RELEASE_BRANCHES < <(git for-each-ref --format='%(refname:short)' refs/heads/release/)

		if (( $${#RELEASE_BRANCHES[@]} == 0 )); then
			echo "No local release branch exists."
			echo "Start one with: make releases"
			exit 1
		fi

		if (( $${#RELEASE_BRANCHES[@]} > 1 )); then
			echo "Multiple release branches exist. Checkout the release you want to finish first:"
			printf '  %s\n' "$${RELEASE_BRANCHES[@]}"
			exit 1
		fi

		RELEASE_BRANCH="$${RELEASE_BRANCHES[0]}"
		git checkout "$$RELEASE_BRANCH"
	fi

	VERSION="$${RELEASE_BRANCH#release/}"
	FILE_VERSION="$$( $(call GET_VERSION) )"

	if [[ "$$FILE_VERSION" != "$$VERSION" ]]; then
		echo "Version mismatch: release branch is $$VERSION but pyproject.toml contains $$FILE_VERSION."
		echo "Fix the version before finishing the release."
		exit 1
	fi

	if [[ -n "$$(git status --porcelain)" ]]; then
		echo "Working tree is not clean. Commit or stash your changes before finishing the release."
		exit 1
	fi

	read -p "Release v$$VERSION message: " message

	if [[ -z "$$message" ]]; then
		echo "Release message is required."
		exit 1
	fi

	git flow release finish \
		-m "release: v$$VERSION - $$message" \
		"$$VERSION"

	git push origin main develop --tags

	echo "Release $$VERSION finished and pushed successfully."


# =========================================================
# HOTFIX
# =========================================================

hotfixs:
	read -p "Hotfix name: " nome

	if [[ -z "$$nome" ]]; then
		echo "Hotfix name is required."
		exit 1
	fi

	git checkout main
	git pull origin main
	git flow hotfix start "$$nome"


hotfixf:
	read -p "Hotfix name: " nome

	if [[ -z "$$nome" ]]; then
		echo "Hotfix name is required."
		exit 1
	fi

	git flow hotfix finish "$$nome"
	git push origin main develop --tags


# =========================================================
# VIRTUAL ENVIRONMENT
# =========================================================

env:
	@echo ""
	@echo "Run the following command in the terminal:"
	@echo "source /var/www/dev/venv/bin/activate"


denv:
	@echo ""
	@echo "To leave the virtual environment, run:"
	@echo "deactivate"


# =========================================================
# BACKUP AND RESTORE — POSTGRESQL
# =========================================================

dbbackup:
	@echo "Preparing database backup..."

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
	echo "Backup created successfully:"
	echo "$$BACKUP_FILE"


dbrestore:
	@echo "Available backups:"
	@echo ""

	mkdir -p "$(BACKUP_DIR)"

	ls -lh "$(BACKUP_DIR)"/*.dump 2>/dev/null || \
		echo "No backups found."

	echo ""
	read -p "Backup path: " BACKUP_FILE

	if [[ ! -f "$$BACKUP_FILE" ]]; then
		echo "File does not exist: $$BACKUP_FILE"
		exit 1
	fi

	echo ""
	echo "WARNING: current data will be replaced."

	read -p "Type 'yes' to continue: " CONFIRMATION

	if [[ "$$CONFIRMATION" != "yes" ]]; then
		echo "Restore cancelled."
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

	echo "Restoring database..."

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
	echo "Database restored successfully."


dbbackups:
	@mkdir -p "$(BACKUP_DIR)"
	@echo "Available backups:"
	@ls -lh "$(BACKUP_DIR)"/*.dump 2>/dev/null || \
		echo "No backups found."


# =========================================================
# PROCESSES / PORTS
# =========================================================

kill:
	@read -p "Port: " port; \
	pid=$$(sudo lsof -t -i:$$port); \
	if [ -n "$$pid" ]; then \
		echo "Terminating process $$pid on port $$port..."; \
		sudo kill -9 $$pid; \
	else \
		echo "No process found on port $$port."; \
	fi