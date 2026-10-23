# Milestones

Each finished milestone gets a dated entry under **Log** and its own git commit.

## Plan
- [x] **M0: Project setup.** Git repo, `CLAUDE.md`, ADRs (stack, domain mapping), subagents adapted to Flask + Bootstrap, this plan.
- [x] **M1: Flask skeleton.** App factory, config, SQLite + models (`User`, `Student`, `Absence`) with FKs/CHECKs, `init-db` command that creates the admin, Bootstrap `base.html`, pytest setup.
- [x] **M2: Authentication.** Login/logout page, `admin`/`assistant` roles, role-required decorators, CSRF.
- [x] **M3: Assistant management (admin).** Add and remove lab assistants. Removing one reassigns their students.
- [ ] **M4: Students (WAD "customers").** Add/edit/delete student, students page, student profile page. Assistants are scoped to their own students.
- [ ] **M5: Absences (WAD "licenses").** Create-absence page, absences page with a filter by student, revoke, extend. Scoped per assistant.
- [ ] **M6: Public absence form.** Students report a Tue/Thu 18–20 absence with a reason, without logging in.
- [ ] **M7: Validation API.** `GET /api/v1/validate?student_number=…&date=…`.
- [ ] **M8: Polish + submission.** Tests for all invariants, demo seed data, README with run instructions and screenshots.

## Open questions
- M6: how does a public-form submission find its assistant? (See `adr/shared/shared-domain-mapping.md`.)

## Log
### M3: Assistant management (2026-10-23)
- `services/assistants.py`:
  - `list_assistants` (with student counts) and `create_assistant` (case-insensitive duplicate-email check).
  - `remove_assistant`: moves the students (and so their absences) to another assistant and deletes the assistant in **one transaction**, rolling back on any error.
- `admin` blueprint (admin only):
  - `GET /admin/assistants`: table plus empty state.
  - `GET/POST /admin/assistants/new`: name, email, temporary password of at least 8 characters.
  - `POST /admin/assistants/<id>/delete`: optional `reassign_to`, which is required when the assistant has students.
- Rules: the target must be a different assistant (not self, not an admin, and it must exist). Removing an admin or a missing id gives 404. With students and no other assistant, the Remove button is disabled.
- UI: a Bootstrap confirmation modal per assistant, with a select listing only the other assistants. Navbar "Assistants" link for admins only. The form macro shows help text (`aria-describedby`).
- Fixed: Jinja macro `kwargs` reassignment broke keyword args (now `attrs`).
- Tests: `test_admin.py` (26 tests, including an atomicity test with a simulated failure after the UPDATE). **67 passed** in total, ruff clean. Also checked end to end with CSRF on.

### M2: Authentication (2026-10-23)
- `auth` blueprint:
  - `GET/POST /login`: Flask-WTF form, CSRF, "remember me", case-insensitive email, the same error for a wrong email or a wrong password.
  - `POST /logout`: CSRF-protected, so a GET returns 405.
- Safe `?next=` redirect after login. It rejects absolute URLs, `//host` and backslash tricks; the backslash case was found by a test and fixed.
- `decorators.py`: `role_required(*roles)` and `admin_required`. Anonymous users are sent to login, and logged-in users with the wrong role get 403.
- `dashboard` blueprint `/dashboard/`: stat cards scoped per role. An assistant sees their own students and active absences. An admin sees everything, plus the assistant count.
- 403/404 error pages. Navbar shows Dashboard, the user name and role badge and a Log out button (POST form) when logged in, and Staff login otherwise.
- `_macros/forms.html` `render_field` (Bootstrap labels plus `is-invalid`/`invalid-feedback`).
- Session cookies are HttpOnly with SameSite=Lax. `init-db` normalizes the admin email.
- Tests: `test_auth.py` (22 tests, including CSRF on and off). **41 passed** in total, ruff clean. Also checked end to end with CSRF on.

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
