# STEP: current progress

Updated: 2026-10-23. The full plan and the per-milestone log are in `MILESTONES.md`.

## Current milestone
**M1: Flask skeleton.** Done and pushed. Next up is **M2: Authentication**.

## Done
- **M0:** `CLAUDE.md`, `MILESTONES.md`, `STEP.md`, `adr/` (stack + domain mapping), 12 subagents adapted to Flask/Bootstrap, scope-guard updated, git on top of `origin/main` with the repo-local author `adrianmihaipopescu2005`.
- **M1:**
  - Flask app factory, config, extensions.
  - Models `User`/`Student`/`Absence` with FK and CHECK constraints, and `Absence.covers(date)`.
  - The `flask init-db` command.
  - `base.html` with Bootstrap 5.3.3 and a home page.
  - pytest: 19 tests pass, ruff clean.

## Next
1. **M2: Authentication.**
   - `auth` blueprint with a login/logout page (Flask-WTF form, CSRF).
   - `admin_required`/`login_required` role decorators.
   - Navbar links per role, and a dashboard landing page after login.
   - Tests: login success/failure, logout, anonymous users redirected, assistant blocked from admin routes.
2. Then M3 (assistants) → M4 (students) → M5 (absences) → M6 (public form) → M7 (API) → M8 (polish).

## Blocked / open questions
- **M3:** what happens to an assistant's students when the admin removes that assistant? (For now the delete is blocked.) Options: block it, reassign the students to another assistant, or delete them too.
- **M6:** how does a public-form submission find its assistant? (For example, by matching `student_number` against registered students.)

## Decisions so far
- The absence app is mapped onto the WAD spec: admin = professor, seller = lab assistant, customer = student, license = absence.
- Students use a public form with no login. Revoke = reject/cancel. Extend = covers more weekly sessions.
- The API checks whether a student is excused on a given date.
- Stack: Flask + Bootstrap 5 + SQLite. Milestones are tracked in `MILESTONES.md` + git, and the current state here in `STEP.md`.
- Templates/static live in `frontend/`, and the Flask app in `backend/app/`.
- Deleting a student also deletes their absences (CASCADE). Revoking an absence never deletes it.

## How to run (from `backend/`)
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\flask --app app init-db
.venv\Scripts\flask --app app run --debug
.venv\Scripts\python -m pytest
```
