# Lab Absence Manager

A web app where students tell their lab assistant that they can't attend a **Mobile Systems and
Applications** lab session (**Tuesday 18–20** or **Thursday 18–20**), and why. Lab assistants and
the professor manage students and absences on a dashboard, and other programs can check through
an API whether a student is excused.

It's built for the **Web Application Design (WAD)** project. The WAD "software license dashboard"
spec is mapped onto absences (see [the mapping](#how-the-wad-requirements-map-onto-this-app)).

**Stack:** Python 3.11, Flask 3, Flask-SQLAlchemy (SQLite), Flask-Login, Flask-WTF ·
HTML, CSS, vanilla JavaScript, Bootstrap 5.3.

## Quick start

From the `backend/` folder (Windows; on macOS/Linux use `.venv/bin/` instead of `.venv\Scripts\`):

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\flask --app app seed-demo          # demo data (or: init-db, see below)
.venv\Scripts\flask --app app run --debug
```

Then open <http://127.0.0.1:5000>.

### Demo accounts (`seed-demo`)

| Role | Email | Password |
|------|-------|----------|
| Admin (professor) | `prof@demo.local` | `demo-admin-123` |
| Lab assistant | `maria@demo.local` | `demo-pass-123` |
| Lab assistant | `andrei@demo.local` | `demo-pass-123` |

Student numbers for the public form: `LM1001`–`LM1004` (Maria) and `LM2001`–`LM2003` (Andrei).
The demo absences are dated relative to the day you run the command.
`seed-demo` only fills an empty database. `seed-demo --reset` deletes everything first, after asking.

### A real admin account instead

```
.venv\Scripts\flask --app app init-db --email you@example.com --name "Your Name" --password "…"
```

### Configuration (environment variables)

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | dev key in `--debug`, otherwise a random key per start | Signs sessions and CSRF tokens. **Set it in production.** |
| `DATABASE_URL` | `sqlite:///backend/instance/app.db` | Database location |
| `COOKIE_SECURE` | off | Set to `1` when serving over HTTPS |

## How the WAD requirements map onto this app

| WAD spec | This app |
|----------|----------|
| System admin | **Admin** = the professor. Adds and removes lab assistants, sees everything. |
| Seller | **Lab assistant**. Sees and changes only their own students and those students' absences. |
| Customer | **Student**. Belongs to one assistant and has no login. |
| License | **Absence**: student, slot, first missed date, number of weekly sessions, reason, status. |
| Login page | `/login` |
| Add / edit / delete customer, customer profile | `/students/new`, `/students/<id>/edit`, delete on the profile, `/students/<id>` |
| Customers page | `/students/` (search, plus a filter by assistant for the admin) |
| Create license | `/absences/new` (staff) and the public form `/report/` (students) |
| Licenses page (filter by customer, revoke, extend) | `/absences/`: filters for student, status, slot and search. Revoke and extend. |
| Revoke license | Marks the absence *revoked*. It's kept, never deleted. |
| Extend license | Adds weekly sessions (max 14, one semester). |
| Admin: add/remove sellers, everything unrestricted | `/admin/assistants`. Removing an assistant moves their students to another assistant. |
| License validation API | `GET /api/v1/validate` with an API key (see below) |

## Dynamic features (JavaScript, no page reload)

1. **Revoke/extend in place:** on the absences page and the student profile, the row updates
   through `fetch`.
2. **Live search:** the students and absences tables filter as you type.
3. **Smart absence form** (`/report/`):
   - only dates on the slot's weekday are accepted, with a "Use Tuesday …" shortcut;
   - the "covered until" date is shown live;
   - the student number is checked while typing. It shows only initials and group.
4. **Excused-check widget** on the dashboard: calls the validation API and shows the answer instantly.

Every page also works with JavaScript turned off. The forms then submit normally and the server
renders the same result.

## Validation API

Each staff user creates a key on the **API key** page. The key is shown once and stored hashed.

```
curl -H "X-API-Key: lam_…" "http://127.0.0.1:5000/api/v1/validate?student_number=LM1001&date=2026-10-27"
```

```json
{"excused": true, "student_number": "LM1001", "date": "2026-10-27", "lab_day": true,
 "slot": "TUE_18_20", "slot_label": "Tuesday 18–20", "absence_id": 1, "until": "2026-11-03"}
```

| Status | When |
|--------|------|
| 200 | Answer. A day without a lab gives `"lab_day": false, "excused": false`. |
| 400 | Missing `student_number`, or `date` isn't `YYYY-MM-DD` |
| 401 | Missing or invalid `X-API-Key` (and not logged in) |
| 404 | Unknown student, or a student of another assistant (same answer, so nothing leaks) |

Errors are JSON: `{"error": "…"}`. An assistant's key only sees their own students. The admin's
key sees all students.

## Rules the app enforces

- An absence starts on its slot's weekday, at most **30 days ago** and at most **6 months ahead**.
  It covers 1–14 weekly sessions.
- The database enforces these too: foreign keys plus CHECK constraints for role, slot, the
  slot/weekday match, status and sessions.
- Assistants only ever see their own data. This is checked on the server, also for the JSON
  endpoints and the API.
- CSRF protection on every form and every `fetch` POST. Passwords and API keys are stored hashed.
- The public pages are rate-limited per IP address (30 lookups and 10 reports per minute,
  in memory).

## Tests

```
cd backend
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
```

There are 242 tests: models, auth, admin, students, absences, the public form, the API, the demo
data and the hardening fixes.

## Project layout

```
backend/app/          Flask app: models, services/ (business rules), blueprints/ (routes)
backend/tests/        pytest
frontend/templates/   Jinja templates (Bootstrap 5)
frontend/static/      css/, js/ (one file per dynamic feature)
adr/                  architecture decisions
MILESTONES.md         milestone plan and log, STEP.md: current status
```

## Known limitations

- The rate limiter lives in one process's memory. It resets on restart and isn't shared between
  several server processes.
- Behind a reverse proxy, the rate limiter sees the proxy's IP unless the app is configured for
  the proxy (`ProxyFix`).
- The public form identifies students only by student number.
