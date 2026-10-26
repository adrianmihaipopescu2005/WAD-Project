# STEP: current progress

Updated: 2026-10-23. The full plan and the per-milestone log are in `MILESTONES.md`.

## Current milestone
**M5: Absences.** Done and pushed. Next up is **M6: Public absence form** (needs the lookup privacy decision below).

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

## Next
1. **M6: Public absence form.** Plus the dynamic **smart form** (Tue/Thu-only dates, live "covered until" date, student lookup). **Needs both open questions below answered first.**
2. **M7:** validation API plus the dynamic **excused-check widget**.
3. **M8:** polish (demo seed data, README, a manual browser check of every dynamic feature).

## Blocked / open questions
- **M6 smart form:** the student number lookup is public, so how much should it reveal? Initials only / found or not found / no lookup.
- **M6:** how does a public-form submission find its assistant? (For example, by matching `student_number` against registered students.)

## Decisions so far
- The absence app is mapped onto the WAD spec: admin = professor, seller = lab assistant, customer = student, license = absence.
- Students use a public form with no login. Revoke = reject/cancel. Extend = covers more weekly sessions.
- The API checks whether a student is excused on a given date.
- Stack: Flask + Bootstrap 5 + SQLite. Milestones are tracked in `MILESTONES.md` + git, and the current state here in `STEP.md`.
- Dynamic features, a course requirement (decided 2026-10-23): revoke/extend in place, live search, smart absence form, excused-check widget. Vanilla JS `fetch` + JSON, progressive enhancement. See `adr/shared/shared-dynamic-features.md`.
- Templates/static live in `frontend/`, and the Flask app in `backend/app/`.
- Removing an assistant reassigns their students to another assistant chosen by the admin (decided 2026-10-23). The DB keeps `ON DELETE RESTRICT` as a safety net.
- Deleting a student also deletes their absences (CASCADE). Revoking an absence never deletes it.

## How to run (from `backend/`)
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\flask --app app init-db
.venv\Scripts\flask --app app run --debug
.venv\Scripts\python -m pytest
```
