# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Spendly is a lightweight personal expense tracker built with Flask and SQLite. It is built incrementally in numbered steps; each step has a spec in `.claude/specs/NN-<slug>.md` that defines its routes, DB changes, and acceptance criteria. Read the relevant spec before working on a step.

---

## Commands
```bash
# Setup
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run dev server (port 5001 — don't change it)
python app.py

# Tests (pytest.ini sets pythonpath = . so `import app` works from tests/)
pytest
pytest tests/test_07-add-expense.py
pytest -k "test_name"
pytest -s
```

---

## Architecture
```
app.py                 # All routes — single file, no blueprints
database/
  db.py                # Connection + schema + auth helpers: get_db(), init_db(), seed_db(), create_user(), get_user_by_email()
  queries.py           # Expense/profile queries: CRUD on expenses, summary stats, category breakdown, date filtering
templates/             # One template per page, all extend base.html
static/css/            # style.css global; one CSS file per page (landing, profile, add_expense, analytics)
static/js/main.js      # Vanilla JS only
tests/                 # One test file per step, named after the spec
.claude/specs/         # Step specs (source of truth for feature behaviour)
.claude/commands/      # Workflow slash commands (create-spec, test-feature, code-review-feature, ship-feature, seed-*)
.claude/agents/        # Subagents used by those commands (test writer/runner, quality/security reviewers)
```

Key cross-file behaviour:
- **DB location:** `db.DB_PATH` points to `spendly.db` at the repo root. Every helper opens its own connection via `get_db()` and closes it — there is no request-scoped connection.
- **Startup side effects:** importing `app` runs `init_db()` and `seed_db()` inside an app context. `seed_db()` only inserts when `users` is empty (demo login: `demo@spendly.com` / `demo123`).
- **Auth:** session-based. `login` sets `session["user_id"]` and `session["user_name"]`; protected routes check `session.get("user_id")` and redirect to `login` if missing.
- **Ownership:** expense queries in `queries.py` take `user_id` and filter on it; edit/delete call `get_expense_by_id(id, user_id)` and `abort(404)` if it returns `None`.
- **Categories:** the allowed list is the `CATEGORIES` constant in `app.py`; form validation checks against it.
- **Date filtering:** `/profile` accepts `date_from` / `date_to` (`YYYY-MM-DD`) query params validated by `_parse_date()`; `queries._build_date_filter()` builds the parameterized WHERE fragment.
- **Test isolation:** tests `monkeypatch.setattr(database.db, "DB_PATH", tmp_path/...)` and call `init_db()` so they never touch the real `spendly.db`. Follow this pattern in new tests.

**Where things belong:**
- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` (connection/schema/users) or `database/queries.py` (expense and reporting queries) — never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file, not inline `<style>` tags

---

## Routes

| Route | Status |
|---|---|
| `GET /` | Landing page |
| `GET, POST /register` | Implemented (Step 2) |
| `GET, POST /login` | Implemented (Step 3) |
| `GET /logout` | Implemented (Step 3) |
| `GET /profile` | Implemented (Steps 4–6) — stats, transactions, category breakdown, date filter + presets |
| `GET, POST /expenses/add` | Implemented (Step 7) |
| `GET, POST /expenses/<int:id>/edit` | Implemented (Step 8) |
| `POST /expenses/<int:id>/delete` | Implemented (Step 9) — POST only, JS `confirm()` in the profile table |
| `GET /analytics` | Login-guarded placeholder template, no data yet |
| `GET /terms`, `GET /privacy` | Static pages |

Only implement a new step when the active task explicitly targets it.

---

## Code style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always parameterized (`?` placeholders) — never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`; user-facing validation errors use `flash(msg, "error")` and re-render the form with `form=request.form`

---

## Tech constraints

- **Flask only** — no FastAPI, no Django, no other web frameworks
- **SQLite only** — no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** — no React, no jQuery, no npm packages
- **No new pip packages** — work within `requirements.txt` as-is unless explicitly told otherwise; flag it and keep `requirements.txt` in sync if one is ever needed
- Python 3.10+ assumed — f-strings and `match` statements are fine
- **FK enforcement is manual** — `get_db()` must keep running `PRAGMA foreign_keys = ON` on every connection

---

## Feature workflow

Features follow the slash-command pipeline in `.claude/commands/`:
`/create-spec <n> <name>` (requires a clean working tree; creates spec + `feature/<slug>` branch) → implement → `/test-feature <spec-name>` → `/code-review-feature <spec-name>` → `/ship-feature`.

---

## Subagent Policy
- Always use a builtin explore subagent for codebase exploration before implementing any new feature
- Always use a subagent to verify test results after any implementation
- When asked to plan, delegate codebase research to a subagent before presenting the plan
- Always use a builtin plan subagent in plan mode
