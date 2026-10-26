// Dark mode. Loaded in <head> (not deferred) so the theme is applied before the page paints.
// Uses the saved choice, otherwise the system setting. [data-theme-toggle] buttons switch it.
(function () {
  "use strict";

  const KEY = "lam-theme";
  const media = window.matchMedia("(prefers-color-scheme: dark)");

  function saved() {
    try {
      return localStorage.getItem(KEY);
    } catch (err) {
      return null; // storage can be blocked (private mode); then just follow the system
    }
  }

  function preferred() {
    return saved() || (media.matches ? "dark" : "light");
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-bs-theme", theme);
    const dark = theme === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
      button.title = dark ? "Light mode" : "Dark mode";
      const icon = button.querySelector("i");
      if (icon) icon.className = dark ? "bi bi-sun" : "bi bi-moon-stars";
    });
  }

  apply(preferred());
  media.addEventListener("change", () => {
    if (!saved()) apply(preferred());
  });

  document.addEventListener("DOMContentLoaded", () => {
    apply(preferred()); // update the toggle buttons, which didn't exist yet above
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-bs-theme") === "dark"
          ? "light" : "dark";
        try {
          localStorage.setItem(KEY, next);
        } catch (err) {
          // not saved, but still switched for this page
        }
        apply(next);
      });
    });
  });
})();
