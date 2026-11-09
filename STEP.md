# STEP: current progress

Updated: 2026-10-28. The full plan and the per-milestone log are in `MILESTONES.md`.

## Current milestone
**M10: Decision emails.** Committed and pushed, not deployed yet. M9 is deployed on PythonAnywhere (admin, Darian and 38 teams set up by the user).

## Done
- **M0:** `CLAUDE.md`, `MILESTONES.md`, `STEP.md`, `adr/` (stack + domain mapping), 12 subagents adapted to Flask/Bootstrap, scope-guard updated, git on top of `origin/main` with the repo-local author `adrianmihaipopescu2005`.
- **M1:**
  - Flask app factory, config, extensions.
  - Models `User`/`Student`/`Absence` with FK and CHECK constraints, and `Absence.covers(date)`.
  - The `flask init-db` command.
  - `base.html` with Bootstrap 5.3.3 and a home page.
  - pytest: 19 tests pass, ruff clean.
- **M2:**
  - Login/logout (CSRF, safe `next`), `role_required`/`admin_required`.
  - Dashboard with stats scoped per role, 403/404 pages, navbar per role, form macro.
  - 41 tests pass.
- **M3:**
  - Admin pages: list, add and remove lab assistants.
  - Removal moves the students to another assistant in one transaction (confirmation modal).
  - 67 tests pass.
- **M4:**
  - Students list (search, admin filter by assistant), add, edit, delete (cascades absences), profile with an absences table.
  - Scoped per assistant (others' students give 404). The admin picks or reassigns the assistant.
  - 103 tests pass.
- **M5:**
  - Absences page (filters: student, status, slot, search, admin assistant filter), create-absence page (slot/weekday check, 1–14 sessions).
  - Revoke (keeps the row) and extend (active only, max 14).
  - Scoped per assistant. "Add absence" plus revoke/extend on the student profile.
  - **Dynamic:** revoke/extend in place and live search (absences + students) via `fetch`. Every page still works without JS.
  - 150 tests pass. The JS hasn't been tried in a real browser yet.
- **M6:**
  - Public `/report/` form, matched by student number to the student's assistant. Unknown numbers are rejected, duplicate covered sessions are rejected, and a one-time thanks page follows.
  - **Dynamic smart form:** weekday check plus a "next session" shortcut, a live "covered until" date, and a student lookup (initials and group only).
  - 177 tests pass. The JS hasn't been tried in a real browser yet.

- **M7:**
  - `GET /api/v1/validate` with an API key (hashed, shown once, rotate/revoke) or a session. Scoped per assistant (others give 404).
  - API key page with a curl example.
  - **Dynamic excused-check widget** on the dashboard (no-JS fallback).
  - 211 tests pass.
- **M8:**
  - `flask seed-demo`, plus a README.
  - Final review by the 4 reviewer subagents. Every finding is fixed or recorded as accepted.
  - Date window of 30 days back to 6 months ahead, and per-IP rate limit on the public pages.
  - **All 4 dynamic features checked in Chrome**: they work, with no reload and no console errors.
  - 242 tests pass.

- **Restyle (after M8):** "modern clean" theme, dark mode toggle, icons, new home page, subtle animations. Checked in Chrome.
- **M9:**
  - Teams of 2 with a fixed slot replace student numbers. Public form: pick team, then name. Deadline: 23:59 the day before (Romanian time).
  - "Motivated" toggle for admin/assistant; only motivated absences excuse a student. Staff create page removed.
  - Teams page, `flask import-teams` (real list in git-ignored `backend/instance/teams.txt`, 38 teams), seed with Darian.
  - 243 tests pass. The new public-form JS hasn't been tried in a real browser yet.
- **M10:**
  - Required student email on the form. Pending / Motivated / Not motivated buttons; each decision emails the student (Gmail SMTP via `MAIL_*` env vars).
  - `flask reset-absences` to update the deployed DB without losing users/teams.
  - 261 tests pass. Real email sending not tried yet (needs the Gmail app password).

## Next
- Try the new public form and the Motivated toggle in a browser.
- On PythonAnywhere: pull, `flask --app app reset-absences`, add `MAIL_USERNAME`/`MAIL_PASSWORD` to the WSGI file, reload.
- Pick the sending Gmail account and create an app password.
- Optional: screenshots in the README.
- Anything the course or the lab assistant asks for after a demo.

## Blocked / open questions
- None right now.

## Decisions so far
- The absence app is mapped onto the WAD spec: admin = professor, seller = lab assistant, customer = student, license = absence.
- Students use a public form with no login. Revoke = reject/cancel. Extend = covers more weekly sessions.
- The API checks whether a student is excused on a given date.
- Stack: Flask + Bootstrap 5 + SQLite. Milestones are tracked in `MILESTONES.md` + git, and the current state here in `STEP.md`.
- Dynamic features, a course requirement (decided 2026-10-23): revoke/extend in place, live search, smart absence form, excused-check widget. Vanilla JS `fetch` + JSON, progressive enhancement. See `adr/shared/shared-dynamic-features.md`.
- Public form (decided 2026-10-28, replaces the 2026-10-26 student-number matching): students pick their team, then their name. Teams have a fixed slot and one assistant (Darian). The form never creates students.
- Deadline (decided 2026-10-28): report by 23:59 the day before, Europe/Bucharest. Replaces the 30-days-back window.
- Decision (decided 2026-10-28): pending → motivated / not motivated, set by admin or assistant, emailed to the student (email required). Only active + motivated absences excuse. Staff don't create absences.
- Templates/static live in `frontend/`, and the Flask app in `backend/app/`.
- Removing an assistant reassigns their teams to another assistant chosen by the admin (decided 2026-10-23). The DB keeps `ON DELETE RESTRICT` as a safety net.
- Public pages: an in-memory per-IP rate limit and a generic duplicate message (decided 2026-10-26).
- Validation API access: an API key, hashed and shown once (decided 2026-10-26).
- Deleting a team also deletes its students and their absences (CASCADE). Revoking an absence never deletes it.

## How to run (from `backend/`)
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\flask --app app seed-demo      # or: init-db for a real admin
.venv\Scripts\flask --app app run --debug
.venv\Scripts\python -m pytest
```
