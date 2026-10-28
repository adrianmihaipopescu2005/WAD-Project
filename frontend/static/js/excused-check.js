// Excused-check widget (dashboard): asks the validation API and shows the answer without a
// reload. It uses the login session, so no API key is needed in the browser.
// Without JS the form submits to the dashboard, which renders the same result.
(function () {
  "use strict";

  const form = document.getElementById("excused-check");
  const output = document.getElementById("excused-result");
  if (!form || !output) return;

  // Builds the same markup as dashboard/_check_result.html, using textContent only.
  function render(kind, strong, text) {
    const classes = {
      "excused": "success", "not-motivated": "warning", "not-excused": "warning",
      "no-lab": "secondary", "error": "danger",
    };
    const box = document.createElement("div");
    box.className = `alert alert-${classes[kind]} mb-0`;
    box.dataset.result = kind;
    if (strong) {
      const b = document.createElement("strong");
      b.textContent = strong;
      box.append(b, " ");
    }
    box.append(text);
    output.replaceChildren(box);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const params = new URLSearchParams(new FormData(form));
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    output.setAttribute("aria-busy", "true");
    try {
      const r = await App.fetchJson(`${form.dataset.endpoint}?${params}`);
      if (!r.lab_day) {
        render("no-lab", "", `No lab session on ${r.date}. Labs are on Tuesdays and Thursdays.`);
      } else if (r.excused) {
        render("excused", "✓ Excused.",
          `${r.student_name} on ${r.date} (${r.slot_label}), motivated absence #${r.absence_id}, until ${r.until}.`);
      } else if (r.reported) {
        const pending = r.decision === "pending";
        render("not-motivated", pending ? "✗ Not excused yet." : "✗ Not excused.",
          `${r.student_name} reported absence #${r.absence_id} for ${r.date} (${r.slot_label}), ` +
          (pending ? "still pending a decision." : "marked not motivated."));
      } else {
        render("not-excused", "✗ Not excused.", `${r.student_name} on ${r.date} (${r.slot_label}).`);
      }
      history.replaceState(null, "", `${location.pathname}?${params}`);
    } catch (err) {
      render("error", "", err.message);
    } finally {
      button.disabled = false;
      output.removeAttribute("aria-busy");
    }
  });
})();
