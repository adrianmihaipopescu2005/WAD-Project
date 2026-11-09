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
- [x] **M6: Public absence form.** Students report a Tue/Thu 18–20 absence with a reason, without logging in.
  - Dynamic: **smart form** (only valid weekdays, live "covered until" date, student number lookup).
- [x] **M7: Validation API.** `GET /api/v1/validate?student_number=…&date=…`.
  - Dynamic: **excused-check widget** calling the API.
- [x] **M8: Polish + submission.** Tests for all invariants, demo seed data, README with run instructions and screenshots.

- [x] **M9: Teams, deadline and "motivated" (2026-10-28).** Students pick their team and name instead of a student number, report by the day before, and staff tick "motivated".
- [x] **M10: Decision emails (2026-10-28).** Required student email; pending / motivated / not motivated; each decision emails the student.

## Open questions
- None right now. (M6 routing and lookup privacy were decided on 2026-10-26. See the shared ADRs.)

## Log
### M10: Decision emails (2026-10-28)
- User decisions: the student's email is **required** on the public form; staff choose **Motivated** or **Not motivated** (a third state, **Pending**, replaces the unticked checkbox) and the student gets an email either way.
- `absences`: `motivated` replaced by `decision` (CHECK `pending`/`motivated`/`not_motivated`), plus `email` (NOT NULL), `decided_at`, `notified_at`. `Absence.motivated` is now a property.
- `services/mail.py`: stdlib `smtplib` + STARTTLS, settings `MAIL_SERVER/PORT/USERNAME/PASSWORD/SENDER` from env (Gmail app password). Never raises; without `MAIL_USERNAME` it logs and returns False. `MAIL_SUPPRESS` collects emails in `app.extensions["mail_outbox"]` for tests.
- `POST /absences/<id>/decision`: commits the decision, then emails; a failed email returns a warning ("click the same button again to retry") and the row shows "Not emailed". Rows show the decision badge, the student's email and "Emailed".
- Decision filter on the absences page; dashboard "Pending decision" count and "Review N" button; API and excused widget report `decision`.
- `absence-actions.js`: also sends the clicked button's name/value (`FormData(form)` leaves it out).
- `flask reset-absences [--yes]`: recreates only the absences table, so the deployed DB keeps users and teams.
- Tests: **261 passed**, ruff clean. Real Gmail sending not tested (no credentials here); the SMTP failure paths are tested with mocks.

### M9: Teams, reporting deadline, "motivated" (2026-10-28)
- User decisions: one lab assistant (Darian), who doesn't have the students' codes. Students are in **teams of two** with a fixed slot (team list supplied by the user, 38 teams). Students pick their team, then which of the two they are. Report by **23:59 the day before** (Monday for Tuesday, Wednesday for Thursday). Admin and assistant tick **"Motivated"**. Staff don't enter absences.
- Model: new `teams` table (slot CHECK, FK to the assistant `ON DELETE RESTRICT`). `students` now has `team_id` (FK `ON DELETE CASCADE`) and `name`; `student_number`, `first_name`/`last_name`, `email`, `study_group` and `assistant_id` were removed. `absences` got `motivated` (default false) and lost `source`. Scoping goes through `Team.assistant_id`.
- `app/clock.py`: "today" is in Europe/Bucharest, so the deadline holds whatever the server's time zone is. `DAYS_BACK` removed; the window is tomorrow to 183 days ahead.
- Public form: one select grouped by team (works without JS); `smart-form.js` turns it into a team picker plus "which one are you?" radios, checks the team's weekday and the deadline, and offers "Use the next session". One report = one session. Lookup endpoint removed.
- Teams page (`/teams/`) replaces the students pages: list with live search and slot filter, add/edit (rename in place keeps absences; clearing a name deletes that student) and delete (cascades). Student profile at `/students/<id>`.
- Absences: "Motivated" toggle in each row (fetch, in place), "motivated" filter, no staff create page. Dashboard: teams/students, active and "not motivated yet" counts, a "Review N absence(s)" button, excused check by student (select).
- Validation API: `student_id` instead of `student_number`; `excused` needs a motivated absence; new `reported`/`motivated`/`student_name` fields.
- `flask import-teams FILE [--assistant EMAIL]`: parses the pasted format (`|`, tab or 2+ spaces), skips teams that already exist, all-or-nothing on conflicts. The real list is in `backend/instance/teams.txt` (git-ignored); duplicates in the pasted list (4 teams listed twice) were merged and a few names capitalized.
- `seed-demo`: admin + Darian (`darian@lab.local`), 5 made-up teams, 6 absences.
- Tests rewritten for the new model (`test_teams.py` replaces `test_students.py`). **243 passed**, ruff clean. JS syntax checked with JavaScriptCore; **not yet tried in a real browser** (the Chrome extension wasn't connected).

### Restyle: "modern clean" theme + dark mode (2026-10-26)
- User choice: the "modern clean" direction, plus a dark mode toggle, icons, a new home page and subtle animations. See `adr/frontend/frontend-theme.md`.
- `static/css/app.css` rewritten around `--lam-*` color tokens on top of Bootstrap's CSS variables (light and dark):
  - indigo accent, Inter font, soft gray page, rounded cards with soft shadows;
  - tables shown as cards, soft status badges, focus rings.
- `static/js/theme.js`: dark mode from the saved choice or the system setting, applied before paint. The toggle has `aria-pressed`.
- `base.html`: frosted white navbar with a brand mark, icon nav links, a user chip with an avatar, and the theme toggle. Bootstrap Icons 1.11.3 (SRI) and Inter loaded.
- Home page: a hero with a "Report an absence" call to action, lab-session pills, and "How it works" in 3 steps.
- Dashboard: welcome header, stat cards with colored icons, and the excused-check card. Page headers with subtitles on the lists. Login and all forms are shown as cards. Empty states have icons, error pages are restyled, and the student profile has an avatar.
- Animations: alerts and live-search results fade in, and rows updated by revoke/extend flash. All of them are off with `prefers-reduced-motion`.
- Checked in Chrome in light and dark mode (home, dashboard, absences, profile). Fixed during the check: the cramped absences filter row (search now has its own row), dates wrapping inside cells, button icons wrapping, and "Welcome back, Prof." (now the full name). No console errors.
- README: every command written for PowerShell (`cd backend`, `.\.venv\Scripts\flask …`), plus the theme mentioned.
- 242 tests still pass.

### M8: Polish, review fixes, browser check (2026-10-26)
- **`flask seed-demo`** (`app/seed.py`): an admin, 2 assistants, 7 students and 6 absences, dated relative to today, in one transaction. It only fills an empty database. `--reset` asks first.
- **Final review** by the 4 reviewer subagents: no blockers. Fixed:
  - Absence date window (user decision): 30 days back to 183 days ahead, on both forms and in the service. This fixes a year-9999 date that crashed staff pages. "Today" comes from `app/clock.py`, which the tests pin to 2026-10-26.
  - Public abuse (user decision): an in-memory per-IP rate limit (`app/ratelimit.py`, 30 lookups and 10 report POSTs per minute) and a generic duplicate message. The public overlap check now covers the whole new range.
  - No public fallback `SECRET_KEY`: a dev key only in debug/testing, otherwise a random key plus a warning. `COOKIE_SECURE` env flag.
  - Errors: a generic error page for 400/405/429/500. `/api/` always answers JSON, and a fetch with an expired session gets a JSON 401.
  - `commit_or_rollback()` on every write. `generate_key` rolls back and keeps the old key. UNIQUE races become form errors.
  - Login checks a dummy hash for unknown emails (same timing). `last_used_at` is written at most once a minute. `parse_day` accepts only `YYYY-MM-DD`. Search escapes LIKE wildcards.
  - JS: server date errors stay visible with the smart form. Lookup results are never stale. Revoke/extend only re-enables controls that were enabled, and focus moves to the updated row. Live search keeps `aria-busy` correct.
  - Templates: confirmation modals for regenerating/revoking an API key, `aria-live` result counters, `aria-current` in the navbar, `aria-describedby`/`aria-invalid` on the date field, no duplicate `id="csrf_token"`, an inline style moved to `app.css`, `min`/`max` on the date pickers, and the student-form select uses the macro.
  - Reviewer notes left as they are: fragments and macros don't extend `base.html` (intended); templates use `is_admin`, which means `role == 'admin'`; a duplicate student number reveals that the number exists (needed for uniqueness).
- **Browser check (Chrome) of all 4 dynamic features, all working with no page reload and no console errors:**
  - Smart form: weekday error, "Use Tuesday" shortcut, live coverage, lookup found/not found/cleared, real submission.
  - Live search on absences and students.
  - Extend and revoke in place, with an alert and focus kept.
  - Excused widget: excused, not excused, no lab day, and another assistant's student showing "not found".
  - Fixed "Thanks, B. M.." (double period) found during the check.
- **README.md**: quick start, demo accounts, configuration, WAD mapping, dynamic features, API docs, rules, tests, layout, known limitations.
- Tests: `test_seed.py` (4) and `test_hardening.py` (27). **242 passed** in total, ruff clean, `node --check` OK.

### M7: Validation API + excused-check widget (2026-10-26)
- `GET /api/v1/validate?student_number=…&date=YYYY-MM-DD` (`api` blueprint, `services/validation.py`). Returns `{student_number, date, lab_day, slot, slot_label, excused, absence_id, until}`. Errors are 400/401/404/405 as `{"error"}`.
- Access (decision of 2026-10-26): an **API key** in `X-API-Key`, or the staff login session.
  - Keys are `lam_…` and only their SHA-256 is stored, in the new `api_keys` table (FK CASCADE, one per user). `last_used_at` is recorded.
  - The key is shown once (`Cache-Control: no-store`). Regenerating replaces the old key, and keys can be revoked.
- Scoping: an assistant key sees only its own students. Others give the same 404 as an unknown number. An admin key sees all.
- "API key" page `/account/api-key`: generate/revoke, status and last use, plus a curl example and the response format. Navbar link.
- **Dynamic excused-check widget** on the dashboard (`static/js/excused-check.js`): calls the API with the session and renders the result (excused / not excused / no lab day / error) without a reload. Without JS, the GET form renders the same result server-side (`dashboard/_check_result.html`).
- ADR `adr/backend/backend-validation-api.md`.
- Tests: `test_api.py` (34 tests: auth, key hashing/rotation/revoke, scoping, covered weeks, revoked, other slot, non-lab day, bad params, key page, widget with and without JS). **211 passed** in total, ruff clean, `node --check` OK. The JS has **not yet been tested in a real browser**.

### M6: Public absence form + smart form (2026-10-26)
- `public` blueprint (no login, CSRF on):
  - `GET/POST /report/`: student number, slot, first missed date, sessions, reason.
  - `GET /report/thanks`: a one-time summary from the session, initials only.
  - `GET /report/lookup.json`.
- Routing (decision of 2026-10-26): the submission is matched by the exact student number (whitespace stripped) to the registered student, so it reaches their assistant. Unknown numbers are rejected. It's stored with `source = 'public'` and never creates students.
- Rejects a duplicate report for a session that an **active** absence of the same slot already covers. After a revoke, the student can report again.
- `AbsenceFieldsForm` (slot, date with the weekday validator, sessions, reason) is shared by the staff form and `PublicAbsenceForm`.
- **Dynamic smart form** (`static/js/smart-form.js`, no reload):
  - Weekday check per slot, plus a "Use Tuesday/Thursday <next date>" shortcut.
  - Live "Covers N sessions: … until …" (UTC date math, so time zones never shift the day).
  - Debounced student-number lookup showing "✓ Found: A. P. · group 2.1" or "not found".
  - The server re-validates everything, and the form works without JS.
- Privacy (decision of 2026-10-26): the lookup and the thanks page reveal **initials and group only**, never the full name, email or assistant. A test checks this.
- Home page: "Report an absence" button.
- Tests: `test_public.py` (27 tests). **177 passed** in total, ruff clean, `node --check` OK. The JS has **not yet been tested in a real browser**.

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
