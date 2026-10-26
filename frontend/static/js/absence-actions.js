// Revoke/extend in place: <form class="js-absence-action"> posts with fetch and the server
// returns the re-rendered table row, which replaces the old one. No page reload.
//   data-confirm: (optional) question to confirm before sending
// Uses event delegation, so rows replaced by live search keep working.
// Without JS these are normal POST forms that redirect back.
(function () {
  "use strict";

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("form.js-absence-action");
    if (!form) return;
    event.preventDefault();

    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) return;

    const row = form.closest("tr");
    const body = new FormData(form); // read before disabling: disabled inputs aren't sent
    const controls = row.querySelectorAll("button, input");
    controls.forEach((el) => { el.disabled = true; });

    try {
      const data = await App.fetchJson(form.action, { method: "POST", body });
      row.outerHTML = data.html;
      App.showAlert(data.message, "success");
    } catch (err) {
      controls.forEach((el) => { el.disabled = false; });
      App.showAlert(err.message, "danger");
    }
  });
})();
