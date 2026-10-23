# Flask + Bootstrap 5 + SQLite

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** stack, flask, bootstrap, sqlite, constraints
- **Related:** [shared-domain-mapping.md](shared-domain-mapping.md)

## Context
The WAD course requires HTML, CSS, JavaScript, Python, Flask and Bootstrap 5.

## Decision
- The backend is Flask with Flask-SQLAlchemy, Flask-Login (sessions) and Flask-WTF (forms + CSRF).
- The database is SQLite, with `PRAGMA foreign_keys=ON` on every connection.
- The frontend is server-rendered Jinja templates with Bootstrap 5 from a CDN, plus small vanilla JS files. There's no SPA framework.
- The templates live in `frontend/templates`, and static files in `frontend/static`. The Flask app is in `backend/app` and points its `template_folder`/`static_folder` at them.
- Tests use pytest, against an in-memory SQLite database.

## Consequences
- Nothing has to be installed beyond Python and pip.
- SQLite serializes writes. That's fine at course-project scale.

## Open questions
- None.
