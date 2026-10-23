# Milestones

Each finished milestone gets a dated entry under **Log** and its own git commit.

## Plan
- [x] **M0: Project setup.** Git repo, `CLAUDE.md`, ADRs (stack, domain mapping), subagents adapted to Flask + Bootstrap, this plan.
- [x] **M1: Flask skeleton.** App factory, config, SQLite + models (`User`, `Student`, `Absence`) with FKs/CHECKs, `init-db` command that creates the admin, Bootstrap `base.html`, pytest setup.
- [ ] **M2: Authentication.** Login/logout page, `admin`/`assistant` roles, role-required decorators, CSRF.
- [ ] **M3: Assistant management (admin).** Add and remove lab assistants.
- [ ] **M4: Students (WAD "customers").** Add/edit/delete student, students page, student profile page. Assistants are scoped to their own students.
- [ ] **M5: Absences (WAD "licenses").** Create-absence page, absences page with a filter by student, revoke, extend. Scoped per assistant.
- [ ] **M6: Public absence form.** Students report a Tue/Thu 18–20 absence with a reason, without logging in.
- [ ] **M7: Validation API.** `GET /api/v1/validate?student_number=…&date=…`.
- [ ] **M8: Polish + submission.** Tests for all invariants, demo seed data, README with run instructions and screenshots.

## Open questions
- M3: what happens to an assistant's students when the admin removes that assistant? (For now the DB blocks the delete with `ON DELETE RESTRICT`.)
- M6: how does a public-form submission find its assistant? (See `adr/shared/shared-domain-mapping.md`.)

## Log
### M1: Flask skeleton (2026-10-23)
- `backend/requirements.txt` (pinned) and `pyproject.toml` (pytest + ruff config).
- App factory `create_app()` that serves templates/static from `frontend/`. The DB defaults to `backend/instance/app.db`.
- Extensions: SQLAlchemy (SQLite `PRAGMA foreign_keys=ON` on every connection), Flask-Login, CSRFProtect.
- Models, with DB-level constraints:
  - `User`: role CHECK `admin`/`assistant`, hashed passwords.
  - `Student`: unique `student_number`, FK to the assistant `ON DELETE RESTRICT`.
  - `Absence`: FK to the student `ON DELETE CASCADE`, slot CHECK, slot/weekday CHECK, `sessions_count >= 1`, status `active`/`revoked`, source `public`/`assistant`, plus `covers(date)` for the validation API.
- `flask init-db` creates the tables and the admin (idempotent).
- `main` blueprint: `/` (home page listing the slots) and `/health`.
- `frontend/templates/base.html` (Bootstrap 5.3.3 with SRI, navbar, flash messages, footer), `main/index.html`, `static/css/app.css`.
- Tests: `conftest.py` (in-memory DB, admin/assistant fixtures), `test_smoke.py`, `test_models.py`. **19 passed**, ruff clean.

### M0: Project setup (2026-10-23)
- Initialized the git repo on top of `origin/main` (adrianmihaipopescu2005/WAD-Project), with a repo-local author and `.gitignore`.
- Added `STEP.md` (done / next / blocked tracker).
- Added `CLAUDE.md` (constraints, invariants, layout, commands).
- Added the ADR scaffold, plus `shared-stack.md` and `shared-domain-mapping.md`.
- Rewrote the 12 `be-*`/`fe-*` subagents for Flask/pytest/SQLite and Jinja/Bootstrap.
- scope-guard: frontend agents may now read `backend/app/blueprints` (for route names and template context).
