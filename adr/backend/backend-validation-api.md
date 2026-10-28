# Validation API and API keys

- **Status:** Accepted
- **Date:** 2026-10-26
- **Tags:** api, validation, api-key, auth, scoping, json
- **Related:** [../shared/shared-domain-mapping.md](../shared/shared-domain-mapping.md), [../shared/shared-dynamic-features.md](../shared/shared-dynamic-features.md)

## Context
WAD asks for an API that "validates the license before running the software". Here that means: is a student excused from the lab session on a given date? The user chose API-key access (2026-10-26).

## Decision
- `GET /api/v1/validate?student_id=…&date=YYYY-MM-DD`, JSON only. (Was `student_number` until 2026-10-28, when student numbers were removed.)
- Auth: an `X-API-Key` header, or the staff login session (used by the dashboard widget). A key that is sent but invalid gets 401, even when there is a session.
- Keys: one per user, `lam_` + 32 random URL-safe bytes. Only the SHA-256 hash is stored (`api_keys`, unique `user_id`, FK `ON DELETE CASCADE`). The key is shown once, when generated. Generating a new key replaces the old one, and keys can be revoked. `last_used_at` is recorded.
- Scoping: an assistant's key only sees their own students. Another assistant's student gets the **same 404 as an unknown number**, so nothing leaks. An admin's key sees everyone.
- Response 200: `{student_id, student_name, date, lab_day, slot, slot_label, excused, reported, motivated, decision, absence_id, until}`. `excused` needs an active absence marked motivated; `reported` is true for any active absence covering the day. A non-lab day gives `lab_day: false`, `excused: false`.
- Errors `{"error": …}`: 400 (missing or non-numeric student_id, bad date), 401 (no or invalid key), 404 (unknown or not visible student), 405 (non-GET).

## Consequences
- External programs can check absences without a staff password.
- A lost key can't be recovered, only replaced.

## Open questions
- None.
