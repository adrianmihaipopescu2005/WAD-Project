# Lab Absence Manager

A web app where students report that they can't attend a lab session of **Mobile Systems and Applications** (slots: **Tuesday 18–20** and **Thursday 18–20**) and give a reason. It's built to also satisfy the **Web Application Design (WAD)** project, whose license-dashboard spec is mapped onto the absence domain (see `adr/shared/shared-domain-mapping.md`).

The milestone plan and log are in `MILESTONES.md`. The current state (done / next / blocked) is in `STEP.md`. Update both after every step.

## Hard constraints
- Stack: **Python + Flask** backend, **HTML/CSS/JavaScript + Bootstrap 5** frontend. No PHP, no Firebase, no NoSQL, no SPA frameworks (React/Vue/Angular).
- Database: **SQLite** through Flask-SQLAlchemy. Relational only: every relation has a foreign key (`PRAGMA foreign_keys=ON`), and each multi-step write runs in one transaction.
- Two logged-in roles only: `admin` (professor) and `assistant` (lab assistant). Students do **not** have accounts. They use the public absence form.

## Invariants
- An assistant sees and changes **only** their own students and those students' absences. An admin sees and changes everything.
- Only an admin can add or remove assistants.
- `absences.slot` is one of `TUE_18_20`, `THU_18_20`, and `start_date` falls on that slot's weekday.
- `absences.sessions_count >= 1`. "Extend" increases it, so the absence covers the next weekly sessions of the same slot.
- `absences.status` is `active` or `revoked`. "Revoke" sets `revoked` and is never a hard delete.
- Every role check is enforced server-side, not just hidden in the UI.

## Layout
- `backend/app/`: app factory (`__init__.py`), `config.py`, `extensions.py`, `models.py`, `services/`, `blueprints/<feature>/routes.py`
- `backend/tests/`: pytest
- `frontend/templates/`: Jinja templates (`base.html`, `<feature>/*.html`)
- `frontend/static/`: `css/`, `js/`
- `adr/`: architecture decisions (`backend/`, `frontend/`, `shared/`, each with an `INDEX.md`)

## Commands (run from `backend/`)
- Install: `python -m venv .venv` then `.venv\Scripts\pip install -r requirements.txt`
- Run: `.venv\Scripts\flask --app app run --debug`
- Init DB + admin: `.venv\Scripts\flask --app app init-db`
- Tests: `.venv\Scripts\python -m pytest`
- Lint: `.venv\Scripts\python -m ruff check .`
