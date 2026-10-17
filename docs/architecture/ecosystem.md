# The Mytech / RESAAS ecosystem

Four repositories, two reusable frameworks and one application built on them.

| Repository | What it is | Language | Distributed as | Consumed by |
|---|---|---|---|---|
| [`django_resaas`](https://github.com/metanochava/django_resaas) | Backend framework: tenancy (Entity → Branch), auth, 2FA, permissions, BaseAPIView, Schema 1.0, files/PDF, notifications | Python / Django / DRF | PyPI `django_resaas` (commercial licence from 0.0.631) | `back` |
| [`quasar_resaas`](https://github.com/metanochava/quasar_resaas) | Frontend framework: BaseStore, AutoCrud/forms, API client, error/alert funnel, auth pages, s-* components | Vue 3 / Quasar / Pinia | git dependency `github:metanochava/quasar_resaas` (the npm registry copy is obsolete) | `front` |
| [`back`](https://github.com/metanochava/back) | Mytech backend: business modules `hr`, `saude`, `farmacia`, `inventory`, `sales`, `purchases`, `accounting`, `crm`, `workflow` | Python / Django | not packaged; deployed from the checkout | `front` (HTTP) |
| [`front`](https://github.com/metanochava/front) | Mytech frontend: module pages, EntityType sites, public sites by domain | Vue 3 / Quasar | `quasar build` → `dist/spa` | browsers |

## Dependency direction

```text
        django_resaas  <──── HTTP contract (REST, Schema 1.0, error contract) ────  quasar_resaas
              ▲                                                                       ▲
              │ pip (django_resaas>=0.0.659)                                          │ npm (git, pinned commit in package-lock.json)
              │                                                                       │
             back  <───────────────────────── HTTP ──────────────────────────────── front
```

- The frameworks never import the application. `back` modules depend on `django_resaas`
  abstractions only; `front` pages depend on `quasar_resaas` exports (`.`, `./auto-imports`,
  `./core/*`).
- Horizontal modules (`inventory`, `sales`, `purchases`, `accounting`, `crm`, `workflow`) do not
  import vertical ones (`saude`, `farmacia`); verticals integrate through services and events.
- Test-time only: `quasar_resaas/i18n.spec.js` reads the translation dictionaries of a sibling
  `django_resaas` checkout (skipped when it is absent); the error-contract fixture in
  `quasar_resaas/tests/fixtures/` holds real `django_resaas` responses.

## Versions actually installed (2026-10-17)

| Where | django_resaas | quasar_resaas |
|---|---|---|
| Source (`/var/www/lib`) | 0.0.659 | 0.0.1456 |
| dev back venv | 0.0.656 | - |
| pro back venv | 0.0.646 | - |
| `front` lockfile | - | 0.0.1450 (commit `5cd8a32d`) |

Installations behind the source miss the security fixes listed in
`django_resaas/docs/deployment/upgrading.md` (0.0.658 and 0.0.659 close a self-elevation to Root
and a public password change). Upgrade them deliberately, following that page.

## Installing from scratch

```bash
# back (Python 3.10+)
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt "django_resaas>=0.0.659"
cp .env.example .env            # fill it; never commit it
python manage.py migrate
python manage.py resaas_setup   # languages, actions, permissions, frontends

# front (Node 20-28)
npm ci                          # quasar_resaas comes from the pinned commit
cp .env.example .env            # API_DEV / API_PRO; values here end up in the bundle
npm run dev
```

## Running the checks

| Repository | Command | Notes |
|---|---|---|
| back | `python -m pytest --nomigrations` | every module (`pyproject.toml` testpaths). `--nomigrations` builds the test tables from the models: running the migrations to create the test database takes several minutes. Check the migrations separately: `python manage.py makemigrations --check --dry-run` and `migrate` on an empty database |
| back | `python manage.py check` | |
| front | `npm test` | vitest: route tables by host, every lazy page resolves, EntityType site registration |
| front | `npm run lint`, `npm run build` | |
| django_resaas | `python -m pytest src` | see its `docs/deployment/releases.md` (`make release-check`) |
| quasar_resaas | `npm test`, `make release-check` | |

Each repository has `.github/workflows/ci.yml` (validation only; nothing there deploys). Only
`django_resaas` publishes from CI, after its validation passes.

## Configuration that is public by design

The frontend build inlines `process.env` values into the browser bundle, so `front/.env` must
hold **no secret**. `FRONT_END_KEY` / `FRONT_END_PASSWORD` (the `FEK`/`FEP` headers) identify the
kind of client to `FrontEndMiddleware`; anyone can read them in the bundle and they grant no
permission (see `django_resaas/docs/architecture/middleware.md`). Secrets (database, SMTP,
Twilio, WhatsApp, `OTP_KEY`, `URL_FILE_KEY`, `SECRET_KEY`) live only in `back/.env` on the server.

## Releases and rollback

- `django_resaas`: `make releases` → `make releasef` → `make publish` (PyPI); a broken version is
  yanked and fixed forward (`django_resaas/docs/deployment/releases.md`).
- `quasar_resaas`: `make publish` (runs `release-check`, bumps, tags, pushes).
- `back` / `front`: git flow releases; deployment is manual. Roll back by checking out the
  previous tag and reinstalling the framework version it was validated with; never reinstall an
  older `django_resaas` over migrations that already ran.

## Known gaps

The audit of 2026-10-17 and its open items are in [progress/audit-2026-10.md](../progress/audit-2026-10.md).
