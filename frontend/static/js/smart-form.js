// Smart absence form (public /report page). No page reload:
//  - the date must fall on the chosen slot's weekday, with a "next session" shortcut;
//  - the "covered until" date is shown live from the start date and session count;
//  - the student number is looked up while typing (the server reveals initials and group only).
// The server validates everything again, so the form also works without JS.
(function () {
  "use strict";

  const form = document.getElementById("report-form");
  if (!form) return;

  const numberInput = form.querySelector("#student_number");
  const lookupStatus = document.getElementById("lookup-status");
  const slotSelect = form.querySelector("#slot");
  const dateInput = form.querySelector("#start_date");
  const dateError = document.getElementById("start_date-js-error");
  const nextButton = document.getElementById("next-session");
  const sessionsInput = form.querySelector("#sessions_count");
  const coverage = document.getElementById("coverage");

  const DAY_MS = 24 * 60 * 60 * 1000;
  const LOOKUP_DEBOUNCE_MS = 400;

  // Dates are handled in UTC so that time zones never shift the day.
  function parseDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    return match ? new Date(Date.UTC(+match[1], +match[2] - 1, +match[3])) : null;
  }
  function isoDate(date) {
    return date.toISOString().slice(0, 10);
  }
  function prettyDate(date) {
    return date.toLocaleDateString("en-GB", {
      weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
    });
  }

  function selectedSlot() {
    const option = slotSelect.selectedOptions[0];
    return { weekday: Number(option.dataset.weekday), dayName: option.dataset.dayName };
  }

  function nextSessionFrom(date, weekday) {
    const offset = (weekday - date.getUTCDay() + 7) % 7;
    return new Date(date.getTime() + offset * DAY_MS);
  }

  function clearServerErrors(input) {
    input.parentElement.querySelectorAll("[data-server-error]").forEach((el) => el.remove());
  }

  // --- weekday check + "next session" shortcut ---------------------------------------
  function checkDate() {
    const { weekday, dayName } = selectedSlot();
    const date = parseDate(dateInput.value);
    const today = new Date();
    const base = date || new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()));
    const suggestion = nextSessionFrom(base, weekday);

    let message = "";
    if (date && date.getUTCDay() !== weekday) {
      message = `${isoDate(date)} is not a ${dayName}. Pick a ${dayName}.`;
    }
    dateInput.setCustomValidity(message);
    dateInput.classList.toggle("is-invalid", Boolean(message));
    dateError.textContent = message;
    dateError.hidden = !message;

    const showSuggestion = !date || Boolean(message);
    nextButton.hidden = !showSuggestion;
    nextButton.dataset.value = isoDate(suggestion);
    nextButton.textContent = `Use ${dayName} ${isoDate(suggestion)}`;
    return !message;
  }

  // --- live "covered until" ------------------------------------------------------------
  function updateCoverage() {
    const date = parseDate(dateInput.value);
    const sessions = Number(sessionsInput.value);
    const max = Number(sessionsInput.max) || 14;
    const valid = date && date.getUTCDay() === selectedSlot().weekday &&
      Number.isInteger(sessions) && sessions >= 1 && sessions <= max;
    coverage.hidden = !valid;
    if (!valid) return;
    const end = new Date(date.getTime() + (sessions - 1) * 7 * DAY_MS);
    coverage.textContent = sessions === 1
      ? `Covers 1 session: ${prettyDate(date)}.`
      : `Covers ${sessions} sessions: ${prettyDate(date)} until ${prettyDate(end)}.`;
  }

  function onScheduleChange(event) {
    if (event && event.target === dateInput) clearServerErrors(dateInput);
    checkDate();
    updateCoverage();
  }

  slotSelect.addEventListener("change", onScheduleChange);
  dateInput.addEventListener("input", onScheduleChange);
  dateInput.addEventListener("change", onScheduleChange);
  sessionsInput.addEventListener("input", onScheduleChange);
  nextButton.addEventListener("click", () => {
    dateInput.value = nextButton.dataset.value;
    clearServerErrors(dateInput);
    onScheduleChange();
  });

  // --- student number lookup -------------------------------------------------------------
  let lookupTimer = null;
  let lookupController = null;

  function setLookup(text, className) {
    lookupStatus.textContent = text;
    lookupStatus.className = `form-text ${className}`;
  }

  async function lookup() {
    const number = numberInput.value.trim();
    if (!number) {
      setLookup("", "");
      return;
    }
    if (lookupController) lookupController.abort();
    lookupController = new AbortController();
    setLookup("Checking…", "text-body-secondary");
    try {
      const url = `${form.dataset.lookupEndpoint}?student_number=${encodeURIComponent(number)}`;
      const data = await App.fetchJson(url, { signal: lookupController.signal });
      if (data.found) {
        const group = data.group ? ` · group ${data.group}` : "";
        setLookup(`✓ Found: ${data.initials}${group}`, "text-success");
      } else {
        setLookup("Student number not found. Check it or contact your lab assistant.", "text-danger");
      }
    } catch (err) {
      if (err.name !== "AbortError") setLookup("", "");
    }
  }

  numberInput.addEventListener("input", () => {
    clearServerErrors(numberInput);
    numberInput.classList.remove("is-invalid");
    clearTimeout(lookupTimer);
    lookupTimer = setTimeout(lookup, LOOKUP_DEBOUNCE_MS);
  });

  form.addEventListener("submit", (event) => {
    if (!checkDate()) {
      event.preventDefault();
      dateInput.focus();
    }
  });

  // Initial state (also after a server-side validation error re-renders the form).
  checkDate();
  updateCoverage();
  if (numberInput.value.trim()) lookup();
})();
