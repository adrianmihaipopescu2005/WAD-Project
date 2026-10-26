# Milestones

Each finished milestone gets a dated entry under **Log** and its own git commit.

## Plan
- [x] **M0: Project setup.** Git repo, `CLAUDE.md`, ADRs (stack, domain mapping), subagents adapted to Flask + Bootstrap, this plan.
- [x] **M1: Flask skeleton.** App factory, config, SQLite + models (`User`, `Student`, `Absence`) with FKs/CHECKs, `init-db` command that creates the admin, Bootstrap `base.html`, pytest setup.
- [x] **M2: Authentication.** Login/logout page, `admin`/`assistant` roles, role-required decorators, CSRF.
- [x] **M3: Assistant management (admin).** Add and remove lab assistants. Removing one reassigns their students.
- [x] **M4: Students (WAD "customers").** Add/edit/delete student, students page, student profile page. Assistants are scoped to their own students.
- [x] **M5: Absences (WAD "licenses").** Create-absence page, absences page with a filter by student, revoke, extend. Scoped per assistant.
  - Dynamic: **revoke/extend in place** (fetch, no reload) and **live search** on the absences and students pages.
- [ ] **M6: Public absence form.** Students report a Tue/Thu 18–20 absence with a reason, without logging in.
  - Dynamic: **smart form** (only valid weekdays, live "covered until" date, student number lookup).
- [ ] **M7: Validation API.** `GET /api/v1/validate?student_number=…&date=…`.
  - Dynamic: **excused-check widget** calling the API.
- [ ] **M8: Polish + submission.** Tests for all invariants, demo seed data, README with run instructions and screenshots.

## Open questions
- M6: the public form's student lookup must not leak names. Show initials only, show found / not found, or drop it? (See `adr/shared/shared-dynamic-features.md`.)
- M6: how does a public-form submission find its assistant? (See `adr/shared/shared-domain-mapping.md`.)

## Log
### M5: Absences + first dynamic features (2026-10-26)
- `services/absences.py`:
  - Every query is scoped through a join on Student (an assistant sees only their students' absences).
  - `list_absences`: filters for student, status, slot, a name/number search and (admin) assistant.
  - `create_absence`: slot/weekday check and 1–14 sessions (`MAX_SESSIONS`, one semester).
  - `revoke`: keeps the row, sets `revoked_at`. Revoking twice gives 409.
  - `extend`: only active absences (409 otherwise), at least 1 extra session, capped at 14.
- `absences` blueprint:
  - `GET /absences/`: list with filters.
  - `GET /absences/search.json`: live search.
  - `GET/POST /absences/new`: `?student_id=` preselects the student, and a slot/date mismatch shows as a form error.
  - `POST /absences/<id>/revoke`, `POST /absences/<id>/extend`: JSON for fetch, otherwise a flash message and a redirect to a safe `next`.
- `GET /students/search.json`: live search on the students page. The results are now in the `students/_results.html` partial.
- **Dynamic features (no reload):**
  - `static/js/common.js`: `App.fetchJson` (Accept JSON, `X-CSRFToken` from `<meta name="csrf-token">`, an expired session detected as an HTML response) and `App.showAlert`.
  - `static/js/live-search.js`: debounced 250 ms, aborts stale requests, updates the URL with `history.replaceState`.
  - `static/js/absence-actions.js`: revoke/extend through `fetch`. The server returns the re-rendered `_row.html`, which replaces the row. Event delegation, so it also works on rows added by live search.
  - Every page still works without JS (GET filter forms, POST forms with redirect).
- JSON endpoints return the rendered partial (`{count, html}`), so the markup is written once, in Jinja, and is auto-escaped.
- `wants_json()` helper. The 400/403/404/405 handlers answer `{"error": ...}` to fetch calls, including CSRF failures.
- Student profile: "Add absence" button and revoke/extend in place, using the shared `absences/_table.html` and `_row.html`. Navbar "Absences" link. The form macro uses `form-select` for selects.
- Pinned `WTForms==3.3.0`: tuple `SelectField` choices are deprecated and are removed in 3.4.
- Tests: `test_absences.py` (47 tests: scoping in HTML and JSON, filters, live search incl. escaping, create validation, revoke/extend with and without JS, the max-sessions cap, CSRF through the `X-CSRFToken` header). **150 passed** in total, ruff clean. The JS files pass `node --check`. The JS behaviour has **not yet been tested in a real browser**.

### M4: Students (2026-10-23)
- `services/students.py`:
  - Every query goes through `_visible_to(user)`: an assistant sees only their own students, an admin sees all.
  - `list_students` (active-absence count, admin filter by assistant, search by name or number), `get_student` (None if not visible), `create_student`/`update_student` (unique student number), `delete_student` (absences CASCADE).
- `students` blueprint (`staff_required`, a new decorator alias for admin + assistant):
  - `GET /students/`: list, search, admin assistant filter, empty states.
  - `GET/POST /students/new`, `GET/POST /students/<id>/edit`.
  - `GET /students/<id>`: profile with details and an absences table (slot, from, until, sessions, reason, source, status).
  - `POST /students/<id>/delete`: confirmation modal, CSRF.
- Owner rules: an assistant's new students are always assigned to themselves (no select, and a posted `assistant_id` is ignored). An admin picks the assistant when adding, and can reassign when editing. An admin with no assistants is sent to add one first. Another assistant's student gives **404**.
- `Absence.end_date` (last covered session). `_macros/absences.html` (status badge, source label) for M5. Navbar "Students" link.
- Tests: `test_students.py` (36 tests). **103 passed** in total, ruff clean. Also checked end to end with CSRF on.

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
