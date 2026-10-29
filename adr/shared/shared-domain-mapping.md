# WAD license spec mapped to lab absences

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** domain, roles, wad, absence, api
- **Related:** [shared-stack.md](shared-stack.md)

## Context
One app has to serve as the Mobile Systems and Applications lab-absence tool and also meet the WAD license-dashboard spec.

## Decision
| WAD spec | This app |
|----------|----------|
| System admin | `admin`: the professor. Adds/removes assistants and sees everything. |
| Seller | `assistant`: a lab assistant. Sees only their own teams, their students and those students' absences. |
| Customer | `Student`: a name in a `Team` (1–2 students, a fixed slot, one assistant). Can have a `student` account (decided 2026-10-29). |
| License | `Absence`: a student, a slot (`TUE_18_20`/`THU_18_20`), `start_date`, `sessions_count`, a reason, the student's `email`, a `decision` and a status. |
| Create license | A logged-in student submits an absence on `/report/` (login required since 2026-10-29). Staff don't create absences (decided 2026-10-28). |
| Revoke license | Set `status = revoked` (reject or cancel). |
| Extend license | Increase `sessions_count` (covers more weekly sessions). |
| Licenses page | Absences page: list, filter by student, tick motivated, revoke, extend. |
| Customers page | Teams page: list, add/edit/delete teams, and each student's profile. |
| License validation API | `GET /api/v1/validate?student_id=…&date=YYYY-MM-DD` returns whether the student is excused (an active, motivated absence) for that session. |

## Consequences
- Every page the WAD spec asks for exists, with absence wording.
- The report form and the student pages (`/signup`, `/my/absences`) add pages the spec doesn't have.

- **Teams instead of student numbers (decided 2026-10-28, replaces the 2026-10-26 routing):** there is one lab assistant (Darian), and the assistant doesn't have the students' codes. Students are stored by name in teams of two with a fixed slot. On the public form a student picks their team, then which of the two they are. The absence goes to the team's assistant with the team's slot. The form never creates students; teams are added on the Teams page or with `flask import-teams`. Student numbers, the student lookup and `absences.source` were removed.
- **Deadline (decided 2026-10-28, replaces the 30-days-back window):** a session can be reported until 23:59 the day before (Monday for Tuesday, Wednesday for Thursday), in Europe/Bucharest time, and at most 183 days ahead. A report covers one session; staff can still extend it.
- **Decision + email (decided 2026-10-28, replaces the "motivated" checkbox):** an absence is `pending`, then admin or the assistant marks it `motivated` or `not_motivated`. The public form requires the student's email, and every decision emails the student (SMTP, Gmail app password in env vars; stdlib `smtplib`, no new dependency). The decision is committed before sending; a failed send is shown to staff as a warning and can be retried by clicking the same decision. Only an active, motivated absence counts as excused.
- **Public abuse limits (decided 2026-10-26):** an in-memory rate limit per IP (10 report POSTs per minute, no extra dependency). The public "duplicate report" message is generic, so it doesn't reveal whether a student is already absent.
- **Privacy trade-off (2026-10-28, narrowed 2026-10-29):** the report form lists every student's name by team (now only to logged-in students), and a student can still report in a teammate's name. Accepted: staff check each absence before ticking "motivated". The real team list stays out of git (`backend/instance/`).

- **Student accounts (decided 2026-10-29, replaces "two logged-in roles only"):** students can make an account to see the status of their absences (pending / motivated / not motivated, active / revoked). The decision emails stay. Admin is an auxiliary role; the WAD roles are assistant (seller) and student (customer).
  - An account is a `users` row with role `student`. It is **not** linked to a `Student` row by a foreign key: it sees the absences whose `email` equals the account email. A name-based link would let anyone sign up as a classmate and read their reasons.
  - Sign-up and "forgot password" are the same flow: name + email at `/signup`, then a link emailed to the address (signed with `SECRET_KEY` by `itsdangerous`, valid 24 h, single use because it embeds a fingerprint of the current password hash). The password is chosen on the page that link opens, so no unconfirmed account ever exists and nobody can pre-register someone else's email. The `/signup` answer is the same whether or not the email has an account; staff emails get no link.
  - `/my/absences` (student only): read-only list with a decision filter and counts. Students get 403 on every staff page and on the validation API.
- **Students edit / delete their pending absences (decided 2026-10-29):** on "My absences", a student can edit the date (same slot, same rules as a new report, no overlap with their other absences) and the reason, or delete the whole absence (a real delete: the report is withdrawn). Only while the absence is active, `pending`, and its first session can still be reported (by 23:59 the day before). Decided or revoked absences are locked, so a student can't erase a "not motivated" decision. The conditions are in the `UPDATE`/`DELETE ... WHERE` itself, so if staff decide at the same moment, the student's change is refused. Staff revoke still never deletes.
- **Login first (decided 2026-10-29, replaces reporting without login):** every user logs in first, students and staff alike. `/report/` needs a student login (anonymous → login page, then back to the form; staff → 403). The form no longer asks for an email: the absence gets the account's email, so it always appears on that student's "My absences" and nobody can send decisions to someone else's address. Absences reported before this keep the email typed then; they show up for an account with the same email.
  - Existing databases: `flask upgrade-db` rebuilds `users` (SQLite can't alter a CHECK) with foreign keys off, in one transaction, then runs `PRAGMA foreign_key_check`.

## Open questions
- None.
