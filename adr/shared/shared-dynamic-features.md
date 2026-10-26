# Dynamic features (JavaScript without page reload)

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** dynamic, javascript, fetch, ajax, json, csrf, api
- **Related:** [shared-stack.md](shared-stack.md), [shared-domain-mapping.md](shared-domain-mapping.md)

## Context
The course requires 2–3 dynamic features, meaning JavaScript that talks to the Flask backend and updates the page without reloading it. Four were chosen.

## Decision
- The features:
  1. **Revoke/extend in place** (absences page and student profile). `fetch` POST, then the row's status, sessions and "until" date update in place.
  2. **Live search** (students and absences pages). Typing filters the table from a JSON endpoint (debounced about 250 ms).
  3. **Smart absence form** (public form). Only dates on the chosen slot's weekday are accepted, the "covered until" date is shown live, and the student number is looked up before submitting.
  4. **Excused-check widget**. It calls `GET /api/v1/validate` and shows the result instantly.
- Vanilla JS only (`fetch`, no jQuery or frameworks), one file per feature in `frontend/static/js/`, with no inline scripts.
- **Progressive enhancement:** every page works without JS through normal forms and links, and JS only takes over the same actions.
- JSON endpoints use the same role checks and per-assistant scoping as the HTML routes. A JSON request for another assistant's data gets 404.
- POSTs from `fetch` send the CSRF token in the `X-CSRFToken` header (read from `<meta name="csrf-token">` in `base.html`).
- JSON error format: `{"error": "<message>"}` with the matching HTTP status (400/403/404/409).

## Consequences
- Each feature can be demoed by showing that the network tab has no page reload.
- The same service functions serve both the HTML and JSON routes, so the rules aren't duplicated.

- **Smart-form lookup privacy (decided 2026-10-26):** the public lookup reveals only the **initials and group** (for example "A. P. · group 2.1"), never the full name, email or assistant. An unknown number just says "not found".

## Open questions
- None.
