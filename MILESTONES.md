# Milestones

Each finished milestone gets a dated entry under **Log** and its own git commit.

## Plan
- [x] **M0: Project setup.** Git repo, `CLAUDE.md`, ADRs (stack, domain mapping), subagents adapted to Flask + Bootstrap, this plan.
- [ ] **M1: Flask skeleton.** App factory, config, SQLite + models (`User`, `Student`, `Absence`) with FKs/CHECKs, `init-db` command that creates the admin, Bootstrap `base.html`, pytest setup.
- [ ] **M2: Authentication.** Login/logout page, `admin`/`assistant` roles, role-required decorators, CSRF.
- [ ] **M3: Assistant management (admin).** Add and remove lab assistants.
- [ ] **M4: Students (WAD "customers").** Add/edit/delete student, students page, student profile page. Assistants are scoped to their own students.
- [ ] **M5: Absences (WAD "licenses").** Create-absence page, absences page with a filter by student, revoke, extend. Scoped per assistant.
- [ ] **M6: Public absence form.** Students report a Tue/Thu 18–20 absence with a reason, without logging in.
- [ ] **M7: Validation API.** `GET /api/v1/validate?student_number=…&date=…`.
- [ ] **M8: Polish + submission.** Tests for all invariants, demo seed data, README with run instructions and screenshots.

## Open questions
- M6: how does a public-form submission find its assistant? (See `adr/shared/shared-domain-mapping.md`.)

## Log
### M0: Project setup (2026-10-23)
- Initialized the git repo on top of `origin/main` (adrianmihaipopescu2005/WAD-Project), with a repo-local author and `.gitignore`.
- Added `STEP.md` (done / next / blocked tracker).
- Added `CLAUDE.md` (constraints, invariants, layout, commands).
- Added the ADR scaffold, plus `shared-stack.md` and `shared-domain-mapping.md`.
- Rewrote the 12 `be-*`/`fe-*` subagents for Flask/pytest/SQLite and Jinja/Bootstrap.
- scope-guard: frontend agents may now read `backend/app/blueprints` (for route names and template context).
