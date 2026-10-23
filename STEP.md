# STEP: current progress

Updated: 2026-10-23. The full plan and the per-milestone log are in `MILESTONES.md`.

## Current milestone
**M4: Students.** Done and pushed. Next up is **M5: Absences**.

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

## Next
1. **M5: Absences (WAD "licenses").**
   - `absences` blueprint: absences page (list, filter by student, plus status/slot filters), create-absence page (student, slot, start date, sessions, reason).
   - Revoke: POST, sets `revoked`, keeps the row.
   - Extend: POST, adds sessions.
   - Scoped per assistant (only own students' absences; an admin sees all). Server-side check that the date matches the slot's weekday, shown as a form error.
   - "Add absence" button on the student profile (preselects the student). Revoke/extend from the profile too.
   - Tests: scoping, slot/date validation, revoke keeps the row, extend increments, can't extend a revoked absence, CSRF.
2. Then M6 (public form) → M7 (API) → M8 (polish).

## Blocked / open questions
- **M6:** how does a public-form submission find its assistant? (For example, by matching `student_number` against registered students.)

## Decisions so far
- The absence app is mapped onto the WAD spec: admin = professor, seller = lab assistant, customer = student, license = absence.
- Students use a public form with no login. Revoke = reject/cancel. Extend = covers more weekly sessions.
- The API checks whether a student is excused on a given date.
- Stack: Flask + Bootstrap 5 + SQLite. Milestones are tracked in `MILESTONES.md` + git, and the current state here in `STEP.md`.
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
