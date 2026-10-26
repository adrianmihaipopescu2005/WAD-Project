// Live search: a <form data-live-search> filters its results as you type, without a reload.
//   data-endpoint: JSON URL returning {count, html}, with the same query params as the form
//   data-target:   selector of the element whose content is replaced by `html`
//   data-count:    (optional) selector of the element showing `count`
// Without JS the form is a normal GET form, so it still works.
(function () {
  "use strict";

  const DEBOUNCE_MS = 250;

  function queryString(form) {
    const params = new URLSearchParams(new FormData(form));
    for (const [key, value] of [...params]) {
      if (!value) params.delete(key);
    }
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }

  document.querySelectorAll("form[data-live-search]").forEach((form) => {
    const target = document.querySelector(form.dataset.target);
    const counter = form.dataset.count ? document.querySelector(form.dataset.count) : null;
    if (!target) return;

    let timer = null;
    let controller = null;

    async function run() {
      const qs = queryString(form);
      if (controller) controller.abort(); // only the latest request may update the page
      controller = new AbortController();
      target.setAttribute("aria-busy", "true");
      try {
        const data = await App.fetchJson(form.dataset.endpoint + qs, { signal: controller.signal });
        target.innerHTML = data.html;
        if (counter) counter.textContent = data.count;
        history.replaceState(null, "", location.pathname + qs);
      } catch (err) {
        if (err.name !== "AbortError") App.showAlert(err.message, "danger");
      } finally {
        target.removeAttribute("aria-busy");
      }
    }

    function schedule() {
      clearTimeout(timer);
      timer = setTimeout(run, DEBOUNCE_MS);
    }

    form.addEventListener("input", schedule);
    form.addEventListener("change", schedule);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      clearTimeout(timer);
      run();
    });
  });
})();
