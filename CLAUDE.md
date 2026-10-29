# Lab Absence Manager

A web app where students report that they can't attend a lab session of **Mobile Systems and Applications** (slots: **Tuesday 18–20** and **Thursday 18–20**) and give a reason. It's built to also satisfy the **Web Application Design (WAD)** project, whose license-dashboard spec is mapped onto the absence domain (see `adr/shared/shared-domain-mapping.md`).

The milestone plan and log are in `MILESTONES.md`. The current state (done / next / blocked) is in `STEP.md`. Update both after every step.

## Hard constraints
- Stack: **Python + Flask** backend, **HTML/CSS/JavaScript + Bootstrap 5** frontend. No PHP, no Firebase, no NoSQL, no SPA frameworks (React/Vue/Angular).
- Database: **SQLite** through Flask-SQLAlchemy. Relational only: every relation has a foreign key (`PRAGMA foreign_keys=ON`), and each multi-step write runs in one transaction.
- Dynamic features (course requirement): vanilla JS `fetch` + JSON, with no page reload and progressive enhancement. See `adr/shared/shared-dynamic-features.md`.
- Three logged-in roles: `assistant` (lab assistant) and `student` are the main ones; `admin` (professor) is auxiliary. Everyone logs in first. Only a logged-in student can report an absence (`/report/`: pick the team, then their own name); the absence gets the account's email. Staff don't enter absences.

## Invariants
- Students are in **teams** (1–2 students, a fixed slot, one assistant). A student is in exactly one team.
- An assistant sees and changes **only** their own teams, those teams' students and their absences. An admin sees and changes everything.
- Only an admin can add or remove assistants.
- `absences.slot` is one of `TUE_18_20`, `THU_18_20`, and `start_date` falls on that slot's weekday.
- `absences.slot` is the student's team slot.
- A student reports by 23:59 the day before the session (Romanian time): `start_date` is from tomorrow to `DAYS_AHEAD` (183) days ahead. "Today" comes from `app/clock.py` so tests can pin it.
- `absences.decision` is `pending`, `motivated` or `not_motivated`, set by staff after checking the reason. Only an active, motivated absence excuses a student (validation API).
- `absences.email` (the student's) is required. Every decision emails the student (`services/mail.py`, SMTP via `MAIL_*` env vars); a failed email never undoes the decision.
- `absences.sessions_count >= 1`. "Extend" increases it, so the absence covers the next weekly sessions of the same slot.
- `absences.status` is `active` or `revoked`. "Revoke" (staff) sets `revoked` and is never a hard delete.
- A student may edit (date, reason) or delete (a real delete) their **own** absence only while it is active, `pending`, and its first session is still before the reporting deadline. Once staff decide, it is locked. The check is part of the UPDATE/DELETE itself, so a decision saved meanwhile wins.
- A student account sees **only** the absences reported with its email (`absences.email`), read-only. It is created only from a set-password link emailed to that address, so the email is the student's own. Students can't reach any staff page or the validation API.
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
- Upgrade an existing DB in place (keeps data): `.venv\Scripts\flask --app app upgrade-db`
- Load teams: `.venv\Scripts\flask --app app import-teams instance\teams.txt` (real names: keep the file in the git-ignored `instance/`)
- Tests: `.venv\Scripts\python -m pytest`
- Lint: `.venv\Scripts\python -m ruff check .`
