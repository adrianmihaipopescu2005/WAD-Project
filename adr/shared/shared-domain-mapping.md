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
| Seller | `assistant`: a lab assistant. Sees only their own students and those students' absences. |
| Customer | `Student`: belongs to exactly one assistant. Has no login. |
| License | `Absence`: a student, a slot (`TUE_18_20`/`THU_18_20`), `start_date`, `sessions_count`, a reason and a status. |
| Create license | The assistant creates an absence for a student. Students can also submit one through the public form. |
| Revoke license | Set `status = revoked` (reject or cancel). |
| Extend license | Increase `sessions_count` (covers more weekly sessions). |
| Licenses page | Absences page: list, filter by student, revoke, extend. |
| Customers page | Students page: list and view a student's profile. |
| License validation API | `GET /api/v1/validate?student_number=…&date=YYYY-MM-DD` returns whether the student is excused for that session. |

## Consequences
- Every page the WAD spec asks for exists, with absence wording.
- The public form adds a page the spec doesn't have. It creates absences without logging in.

- **Public-form routing (decided 2026-10-26):** a submission is matched by `student_number` against the registered students and goes to that student's assistant. Unknown numbers are rejected ("Student number not found, contact your lab assistant"). Public submissions never create students. They're stored with `source = 'public'`.

## Open questions
- None.
