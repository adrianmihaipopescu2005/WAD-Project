# Visual theme: "modern clean", light and dark

- **Status:** Accepted
- **Date:** 2026-10-26
- **Tags:** theme, css, dark-mode, icons, fonts, animation, bootstrap
- **Related:** [../shared/shared-stack.md](../shared/shared-stack.md)

## Context
The user asked for a more stylish look and chose (2026-10-26) the "modern clean" direction, plus dark mode, icons, a new home page and subtle animations.

## Decision
- Still Bootstrap 5.3.3. The look comes from `static/css/app.css`, which overrides Bootstrap's CSS custom properties. Colors are `--lam-*` tokens, redefined under `[data-bs-theme="dark"]`.
  - Indigo accent `#4f46e5` (white text 6.3:1), a light lavender link color in dark mode, a soft gray page, and white rounded cards with soft shadows.
- Font: Inter (Google Fonts). Icons: Bootstrap Icons 1.11.3 (jsDelivr, pinned with SRI). Every decorative icon has `aria-hidden="true"`.
- Dark mode: `static/js/theme.js`, loaded in `<head>` (not deferred) to avoid a light flash. It uses the saved choice in `localStorage` (`lam-theme`), otherwise the system setting. The navbar toggle keeps `aria-pressed` and `aria-label` in sync.
- Shared building blocks: `.form-card`, `.page-header`/`.page-subtitle`, `.stat-card`/`.stat-icon.tone-*`, `.empty-state`, `.hero`, `.btn-icon`. Every `.table-responsive` is shown as a card.
- Animations: alerts and live-search results fade in, and rows updated by revoke/extend flash. All of them are off under `prefers-reduced-motion`.

## Consequences
- The pages still work without the CDNs (system font, no icons). Only the look degrades.
- New pages should use the building blocks above instead of one-off styles.

## Open questions
- None.
