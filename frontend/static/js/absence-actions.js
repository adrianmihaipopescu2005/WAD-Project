// Revoke/extend/decision in place: <form class="js-absence-action"> posts with fetch and the server
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
    // FormData(form) leaves out the clicked button, which carries e.g. decision=motivated.
    const submitter = event.submitter;
    if (submitter && submitter.name) body.append(submitter.name, submitter.value);
    // Only touch controls that are enabled now, so e.g. a maxed-out Extend stays disabled.
    const controls = [...row.querySelectorAll("button, input")].filter((el) => !el.disabled);
    controls.forEach((el) => { el.disabled = true; });

    try {
      const data = await App.fetchJson(form.action, { method: "POST", body });
      row.outerHTML = data.html;
      // The focused button was replaced with the row; keep keyboard users on the same row.
      const newRow = document.getElementById(`absence-${data.absence.id}`);
      if (newRow) {
        newRow.classList.add("row-flash"); // brief highlight so the change is noticed
        newRow.focus();
      }
      App.showAlert(data.message, data.category || "success"); // "warning" if the email failed
    } catch (err) {
      controls.forEach((el) => { el.disabled = false; });
      App.showAlert(err.message, "danger");
    }
  });
})();
