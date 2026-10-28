# Lab Absence Manager

A web app where students tell their lab assistant that they can't attend a **Mobile Systems and
Applications** lab session (**Tuesday 18–20** or **Thursday 18–20**), and why. Students work in
teams of two with a fixed slot. A student picks their team and their name on a public form, by
23:59 the day before the session. The lab assistant and the professor check each absence and tick
**Motivated**, and other programs can check through an API whether a student is excused.

It's built for the **Web Application Design (WAD)** project. The WAD "software license dashboard"
spec is mapped onto absences (see [the mapping](#how-the-wad-requirements-map-onto-this-app)).

**Stack:** Python 3.11, Flask 3, Flask-SQLAlchemy (SQLite), Flask-Login, Flask-WTF ·
HTML, CSS, vanilla JavaScript, Bootstrap 5.3 + Bootstrap Icons, Inter font.

**Look:** a modern, clean dashboard with a **dark mode** toggle (follows your system setting until
you choose), icons, and subtle animations that are turned off if you prefer reduced motion.

## Quick start

In **PowerShell**, from the project folder. Every `flask` command must be run **from `backend/`**
and **with the `.\.venv\Scripts\` path**, because `flask` is installed only inside the virtual
environment:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\flask --app app seed-demo          # demo data (or: init-db, see below)
.\.venv\Scripts\flask --app app run --debug
```

Then open <http://127.0.0.1:5000>. Keep that window open while you use the app, and stop it with
`Ctrl+C`. On macOS/Linux, use `.venv/bin/flask` instead.

Alternatively, run `.\.venv\Scripts\Activate.ps1` once per terminal, and plain `flask …` works.

### Demo accounts (`seed-demo`)

| Role | Email | Password |
|------|-------|----------|
| Admin (professor) | `prof@demo.local` | `demo-admin-123` |
| Lab assistant | `darian@lab.local` | `demo-pass-123` |

The demo has 5 made-up teams, so the public form works right away. The demo absences are dated
relative to the day you run the command.
`seed-demo` only fills an empty database. `seed-demo --reset` deletes everything first, after asking.

### Real accounts and the real teams

```powershell
.\.venv\Scripts\flask --app app init-db --email you@example.com --name "Your Name" --password "…"
```

Log in as the admin and add the lab assistant on the **Assistants** page. Then load the teams
from a text file:

```powershell
.\.venv\Scripts\flask --app app import-teams instance\teams.txt   # --assistant EMAIL if there are several
```

The file has a `Tuesday:` or `Thursday:` line, then one team per line with the two names separated
by `|`, a tab or two spaces. Running it again skips the teams that already exist. Keep the file
in `backend/instance/`, which git ignores, so real names don't end up in the repository.

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
| Seller | **Lab assistant**. Sees and changes only their own teams, their students and those students' absences. |
| Customer | **Student**. Belongs to a team (2 students, fixed slot) of one assistant. Has no login. |
| License | **Absence**: student, slot, first missed date, number of weekly sessions, reason, motivated, status. |
| Login page | `/login` |
| Add / edit / delete customer, customer profile | Teams: `/teams/new`, `/teams/<id>/edit` (delete there too). Student profile: `/students/<id>` |
| Customers page | `/teams/` (search by name, filter by slot, plus by assistant for the admin) |
| Create license | The public form `/report/` (students only; staff don't enter absences) |
| Licenses page (filter by customer, revoke, extend) | `/absences/`: filters for student, status, motivated, slot and search. Motivated, revoke and extend. |
| Revoke license | Marks the absence *revoked*. It's kept, never deleted. |
| Extend license | Adds weekly sessions (max 14, one semester). |
| Admin: add/remove sellers, everything unrestricted | `/admin/assistants`. Removing an assistant moves their teams to another assistant. |
| License validation API | `GET /api/v1/validate` with an API key (see below) |

## Dynamic features (JavaScript, no page reload)

1. **Motivated/revoke/extend in place:** on the absences page and the student profile, the row
   updates through `fetch`.
2. **Live search:** the teams and absences tables filter as you type.
3. **Smart absence form** (`/report/`):
   - the dropdown of names grouped by team becomes "pick your team", then "which one are you?";
   - only dates on the team's weekday and not past the deadline are accepted, with a
     "Use the next session" shortcut.
4. **Excused-check widget** on the dashboard: calls the validation API and shows the answer instantly.

Every page also works with JavaScript turned off. The forms then submit normally and the server
renders the same result.

## Validation API

Each staff user creates a key on the **API key** page. The key is shown once and stored hashed.

```
curl -H "X-API-Key: lam_…" "http://127.0.0.1:5000/api/v1/validate?student_id=1&date=2026-10-27"
```

```json
{"excused": true, "student_id": 1, "student_name": "Ana Popescu", "date": "2026-10-27",
 "lab_day": true, "slot": "TUE_18_20", "slot_label": "Tuesday 18–20",
 "reported": true, "motivated": true, "absence_id": 1, "until": "2026-10-27"}
```

`excused` is true only for an active absence that staff marked **motivated**. A reported but
unchecked absence gives `"reported": true, "excused": false`. The student id is in the URL of the
student's page (`/students/<id>`).

| Status | When |
|--------|------|
| 200 | Answer. A day without a lab gives `"lab_day": false, "excused": false`. |
| 400 | Missing or non-numeric `student_id`, or `date` isn't `YYYY-MM-DD` |
| 401 | Missing or invalid `X-API-Key` (and not logged in) |
| 404 | Unknown student, or a student of another assistant (same answer, so nothing leaks) |

Errors are JSON: `{"error": "…"}`. An assistant's key only sees their own teams' students. The
admin's key sees all students.

## Rules the app enforces

- A student reports a session on their team's weekday, at the latest by **23:59 the day before**
  (Monday for Tuesday, Wednesday for Thursday, in Romanian time) and at most **6 months ahead**.
  A report covers one session; staff can extend it to up to 14 weekly sessions.
- A student is in exactly one team, and a team has one or two students.
- The database enforces these too: foreign keys plus CHECK constraints for role, slot, the
  slot/weekday match, status and sessions.
- Assistants only ever see their own data. This is checked on the server, also for the JSON
  endpoints and the API.
- CSRF protection on every form and every `fetch` POST. Passwords and API keys are stored hashed.
- The public form is rate-limited per IP address (10 reports per minute, in memory).

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```

There are 243 tests: models, auth, admin, teams (and the import), absences, the public form and
its deadline, the API, the demo data and the hardening fixes.

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
- The public form lists every student's name, so anyone with the link can see who is in which
  team. A student could also report an absence in a teammate's name.
