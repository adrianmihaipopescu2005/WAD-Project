# Dynamic features (JavaScript without page reload)

- **Status:** Accepted
- **Date:** 2026-10-23
- **Tags:** dynamic, javascript, fetch, ajax, json, csrf, api
- **Related:** [shared-stack.md](shared-stack.md), [shared-domain-mapping.md](shared-domain-mapping.md)

## Context
The course requires 2–3 dynamic features, meaning JavaScript that talks to the Flask backend and updates the page without reloading it. Four were chosen.

## Decision
- The features:
  1. **Decision/revoke/extend in place** (absences page and student profile). `fetch` POST, then the row's decision, status, sessions and "until" date update in place (the decision also emails the student).
  2. **Live search** (teams and absences pages). Typing filters the table from a JSON endpoint (debounced about 250 ms).
  3. **Smart absence form** (public form). The names dropdown (grouped by team) becomes a team picker plus "which one are you?" radios, and only dates on the team's weekday that are not past the deadline are accepted (updated 2026-10-28).
  4. **Excused-check widget**. It calls `GET /api/v1/validate` and shows the result instantly.
- Vanilla JS only (`fetch`, no jQuery or frameworks), one file per feature in `frontend/static/js/`, with no inline scripts.
- **Progressive enhancement:** every page works without JS through normal forms and links, and JS only takes over the same actions.
- JSON endpoints use the same role checks and per-assistant scoping as the HTML routes. A JSON request for another assistant's data gets 404.
- POSTs from `fetch` send the CSRF token in the `X-CSRFToken` header (read from `<meta name="csrf-token">` in `base.html`).
- JSON error format: `{"error": "<message>"}` with the matching HTTP status (400/403/404/409).

## Consequences
- Each feature can be demoed by showing that the network tab has no page reload.
- The same service functions serve both the HTML and JSON routes, so the rules aren't duplicated.

- **Smart-form lookup (2026-10-26) removed on 2026-10-28:** with teams there are no student numbers to look up. See the privacy trade-off in [shared-domain-mapping.md](shared-domain-mapping.md).

## Open questions
- None.
