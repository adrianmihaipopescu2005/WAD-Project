# STEP: current progress

Updated: 2026-10-23. The full plan and the per-milestone log are in `MILESTONES.md`.

## Current milestone
**M0: Project setup.** Done and pushed. Next up is **M1**.

## Done
- `CLAUDE.md`: constraints, invariants, layout, commands.
- `MILESTONES.md`: plan M0–M8, plus the log.
- `adr/`: README, TEMPLATE, INDEX files, `shared-stack.md`, `shared-domain-mapping.md`.
- `.claude/agents/`: all 12 `be-*`/`fe-*` agents rewritten for Flask/pytest/SQLite and Jinja/Bootstrap 5.
- `.claude/hooks/scope-guard.mjs`: frontend agents may read `backend/app/blueprints`.

- Git: repo on top of `origin/main` (https://github.com/adrianmihaipopescu2005/WAD-Project), repo-local author `adrianmihaipopescu2005 <adrian.mihai.popescu2005@gmail.com>`, `.gitignore`.

## Next
1. **M1: Flask skeleton.** `backend/requirements.txt`, app factory, config, models (`User`, `Student`, `Absence`), `init-db` command, `frontend/templates/base.html` with Bootstrap 5, pytest `conftest.py`, and a first smoke test.
2. Then M2 (auth) → M3 (assistants) → M4 (students) → M5 (absences) → M6 (public form) → M7 (API) → M8 (polish).

## Blocked / open questions
- **M6:** how does a public-form submission find its assistant? (For example, by matching `student_number` against registered students.)

## Decisions so far
- The absence app is mapped onto the WAD spec: admin = professor, seller = lab assistant, customer = student, license = absence.
- Students use a public form with no login. Revoke = reject/cancel. Extend = covers more weekly sessions.
- The API checks whether a student is excused on a given date.
- Stack: Flask + Bootstrap 5 + SQLite. Milestones are tracked in `MILESTONES.md` + git, and the current state here in `STEP.md`.
