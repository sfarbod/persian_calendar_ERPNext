# Persian Calendar — Agent Instructions

Frappe app that adds Jalali calendar support to ERPNext desk. Targets **Frappe/ERPNext v16** on Python 3.10+.

## Architecture

- **UI**: Jalali datepicker and formatters in browser (`persian_calendar/public/js/jalali_support/`).
- **Backend**: Dates stored and exported as **Gregorian/ISO** — no global Python formatter monkey patches.
- See `docs/jalali_support_v16_fix.md` for export/xlsx constraints.

## Repository layout

```
persian_calendar/          # Python package (hooks, jalali_support, utils)
persian_calendar/public/js/jalali_support/   # Desk JS
docs/                      # Technical notes
cypress/integration/       # E2E specs (require ERPNext)
e2e/                       # Python E2E helpers
```

## Local development (frappe-bench + Docker)

This app lives inside a bench, typically via **frappe_docker** (dev container + MariaDB/Redis services).

| Setting | Value (current dev setup) |
|---------|---------------------------|
| Bench path | `/workspace/development/frappe-bench` |
| Site | `development.localhost` |
| Desk URL | `http://development.localhost:8000` |
| Frappe / ERPNext | v16 |
| DB host (in container) | `mariadb` |

### Install app on bench

```bash
cd $PATH_TO_BENCH
bench get-app https://github.com/sfarbod/persian_calendar_erpnext.git --branch develop
bench --site development.localhost install-app persian_calendar
```

### Common bench commands

```bash
# From bench root
bench --site development.localhost migrate
bench build --app persian_calendar
bench --site development.localhost clear-cache

# Enable tests on site (required for FrappeTestCase)
bench --site development.localhost set-config allow_tests true
```

## Running tests

### Unit / integration tests (from bench root)

```bash
bench --site development.localhost run-tests --app persian_calendar
```

### Pre-commit (from app directory)

```bash
cd apps/persian_calendar
pre-commit install          # once
pre-commit run --all-files  # before commit
```

### Cypress E2E

Prerequisites: Frappe + ERPNext + persian_calendar installed, Jalali Settings enabled, Job Card with Time Logs.

```bash
cd apps/frappe

export CYPRESS_BASE_URL=http://development.localhost:8000
export CYPRESS_ADMIN_PASSWORD=admin

npx cypress run \
  --config-file ../persian_calendar/cypress.config.js \
  --spec ../persian_calendar/cypress/integration/gregorian_stale_jalali_picker.js
```

See `cypress/README.md` for interactive mode and debug trace helpers.

## Dependencies

- Python: `jdatetime>=4.1.2` (see `pyproject.toml`)
- JS bundles: `jalali_support.bundle.js` included via `hooks.py`

## Contributing

- Branch: `develop`
- Run pre-commit before pushing
- Keep changes scoped to Jalali UI or explicit server-side conversion — avoid global Frappe patches

---

## Cursor Cloud specific instructions

Cloud agents run on an isolated Ubuntu VM. They do **not** inherit your local Docker network (`mariadb`, `redis-cache`, etc.).

### First-time cloud setup

1. Ensure this repo is pushed to GitHub (`sfarbod/persian_calendar_erpnext`).
2. Add secrets in **Cursor Dashboard → Cloud Agents → Secrets** (DB passwords, admin password, site URL).
3. `.cursor/environment.json` and `.cursor/Dockerfile` in this repo define the base cloud image.

### What the cloud agent can do in this repo alone

- Edit Python/JS, run `pre-commit`, static analysis
- Run `pip install` for app deps (`jdatetime`)

### What requires full bench context

- `bench run-tests`, `bench migrate`, Cypress E2E
- For full integration testing in cloud, either:
  - Configure Docker-in-Docker and clone/setup frappe-bench in the VM (document commands here as you stabilize them), or
  - Use **My Machines** so commands run on your local dev container that already has bench + two containers

### Suggested cloud verification task

Start with a small scoped task:

```
Run pre-commit on changed files and fix any ruff/eslint issues.
```

Then scale to bench-backed tasks once the cloud environment has bench + site access.

### Install command (runs on every cloud agent start)

Handled by `.cursor/environment.json` → `install` field. Keep it fast and idempotent.

### Do not commit

- `.env`, credentials, `site_config.json` overrides with secrets
- Generated bundles in `persian_calendar/public/dist/` unless intentionally rebuilt
