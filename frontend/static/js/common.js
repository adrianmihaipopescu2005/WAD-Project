// Shared helpers for the dynamic features: a CSRF-aware JSON fetch and inline alerts.
(function () {
  "use strict";

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  // Fetches JSON. Throws an Error with a user-facing message on any failure.
  async function fetchJson(url, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.method && options.method.toUpperCase() !== "GET") {
      headers["X-CSRFToken"] = csrfToken();
    }
    const res = await fetch(url, { credentials: "same-origin", ...options, headers });

    // A redirect to the login page comes back as HTML.
    const type = res.headers.get("Content-Type") || "";
    if (!type.includes("application/json")) {
      throw new Error("Your session may have expired. Reload the page and try again.");
    }
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status}).`);
    }
    return data;
  }

  // Shows a dismissible Bootstrap alert above the page content.
  function showAlert(message, category = "info") {
    const box = document.getElementById("js-alerts");
    if (!box) return;
    const alert = document.createElement("div");
    alert.className = `alert alert-${category} alert-dismissible fade show`;
    alert.setAttribute("role", "alert");
    alert.textContent = message;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close";
    close.setAttribute("data-bs-dismiss", "alert");
    close.setAttribute("aria-label", "Close");
    alert.appendChild(close);
    box.prepend(alert);
  }

  window.App = { fetchJson, showAlert };
})();
