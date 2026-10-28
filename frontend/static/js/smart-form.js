// Smart absence form (public /report page). No page reload:
//  - the one dropdown grouped by team becomes "pick your team" + "which one are you?";
//  - the date must fall on the team's lab day and not be past the deadline (the day before),
//    with a "next session" shortcut.
// The server validates everything again, so the form also works without JS.
(function () {
  "use strict";

  const form = document.getElementById("report-form");
  if (!form) return;

  const field = document.getElementById("student-field");
  const studentSelect = form.querySelector("#student_id");
  const dateInput = form.querySelector("#start_date");
  const dateError = document.getElementById("start_date-js-error");
  const nextButton = document.getElementById("next-session");

  const DAY_MS = 24 * 60 * 60 * 1000;

  // Dates are handled in UTC so that time zones never shift the day.
  function parseDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    return match ? new Date(Date.UTC(+match[1], +match[2] - 1, +match[3])) : null;
  }
  function isoDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function clearServerErrors(container) {
    container.querySelectorAll("[data-server-error]").forEach((el) => el.remove());
  }

  // --- team + member pickers -------------------------------------------------------------
  const teams = [...studentSelect.querySelectorAll("optgroup")].map((group) => ({
    id: group.dataset.team,
    label: group.dataset.teamLabel,
    dayName: group.dataset.dayName,
    weekday: Number(group.dataset.weekday),
    members: [...group.querySelectorAll("option")].map((o) => ({ id: o.value, name: o.textContent })),
  }));

  const teamWrap = document.createElement("div");
  teamWrap.className = "mb-3";
  const teamLabel = document.createElement("label");
  teamLabel.className = "form-label";
  teamLabel.htmlFor = "team-select";
  teamLabel.textContent = "Your team";
  const teamSelect = document.createElement("select");
  teamSelect.className = "form-select";
  teamSelect.id = "team-select";
  teamSelect.append(new Option("Choose your team…", ""));
  for (const dayName of [...new Set(teams.map((t) => t.dayName))]) {
    const group = document.createElement("optgroup");
    group.label = dayName;
    teams.filter((t) => t.dayName === dayName).forEach((t) => group.append(new Option(t.label, t.id)));
    teamSelect.append(group);
  }
  teamWrap.append(teamLabel, teamSelect);

  const memberSet = document.createElement("fieldset");
  memberSet.className = "mb-1";
  memberSet.hidden = true;
  const legend = document.createElement("legend");
  legend.className = "form-label fs-6 mb-1";
  legend.textContent = "Which one are you?";
  const memberChoices = document.createElement("div");
  memberSet.append(legend, memberChoices);

  // The original select stays in the form (it is what gets submitted), just hidden.
  field.querySelector("label[for=student_id]").hidden = true;
  studentSelect.hidden = true;
  field.querySelector(".form-text").hidden = true;
  field.prepend(teamWrap, memberSet);
  // Server errors sit after the hidden select; make sure they still show.
  field.querySelectorAll("[data-server-error]").forEach((el) => el.classList.add("d-block"));

  function selectedTeam() {
    return teams.find((t) => t.id === teamSelect.value) || null;
  }

  function renderMembers(team, checkedId) {
    memberChoices.replaceChildren();
    memberSet.hidden = !team;
    if (!team) return;
    team.members.forEach((m) => {
      const wrap = document.createElement("div");
      wrap.className = "form-check form-check-inline";
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.className = "form-check-input";
      radio.name = "member-choice"; // not submitted: no "name" match on the server
      radio.id = `member-${m.id}`;
      radio.value = m.id;
      radio.checked = m.id === checkedId || team.members.length === 1;
      const label = document.createElement("label");
      label.className = "form-check-label";
      label.htmlFor = radio.id;
      label.textContent = m.name;
      wrap.append(radio, label);
      memberChoices.append(wrap);
    });
    syncStudent();
  }

  function syncStudent() {
    const checked = memberChoices.querySelector("input:checked");
    studentSelect.value = checked ? checked.value : "";
  }

  teamSelect.addEventListener("change", () => {
    clearServerErrors(field);
    renderMembers(selectedTeam(), null);
    onScheduleChange();
  });
  memberChoices.addEventListener("change", () => {
    clearServerErrors(field);
    syncStudent();
  });

  // --- weekday + deadline check, "next session" shortcut ---------------------------------
  function checkDate() {
    const team = selectedTeam();
    const date = parseDate(dateInput.value);
    const earliest = parseDate(dateInput.min);
    let message = "";
    if (team && date && date.getUTCDay() !== team.weekday) {
      message = `${isoDate(date)} is not a ${team.dayName}. Your team's lab is on ${team.dayName}s.`;
    } else if (date && earliest && date < earliest) {
      message = "Too late: absences must be reported by 23:59 the day before the session.";
    }
    dateInput.setCustomValidity(message);
    // Keep the field marked invalid while a server error is shown.
    const serverError = Boolean(dateInput.parentElement.querySelector("[data-server-error]"));
    const invalid = Boolean(message) || serverError;
    dateInput.classList.toggle("is-invalid", invalid);
    dateInput.setAttribute("aria-invalid", String(invalid));
    dateError.textContent = message;
    dateError.hidden = !message;

    // Suggest the team's next session that can still be reported.
    nextButton.hidden = !team || !earliest || (Boolean(date) && !message);
    if (team && earliest) {
      const offset = (team.weekday - earliest.getUTCDay() + 7) % 7;
      const suggestion = new Date(earliest.getTime() + offset * DAY_MS);
      nextButton.dataset.value = isoDate(suggestion);
      nextButton.textContent = `Use the next session: ${team.dayName} ${isoDate(suggestion)}`;
    }
    return !message;
  }

  function onScheduleChange(event) {
    if (event && event.target === dateInput) clearServerErrors(dateInput.parentElement);
    checkDate();
  }

  dateInput.addEventListener("input", onScheduleChange);
  dateInput.addEventListener("change", onScheduleChange);
  nextButton.addEventListener("click", () => {
    dateInput.value = nextButton.dataset.value;
    clearServerErrors(dateInput.parentElement);
    onScheduleChange();
  });

  form.addEventListener("submit", (event) => {
    if (!studentSelect.value) {
      event.preventDefault();
      (selectedTeam() ? memberChoices.querySelector("input") : teamSelect).focus();
      App.showAlert("Choose your team and your name.", "warning");
      return;
    }
    if (!checkDate()) {
      event.preventDefault();
      dateInput.focus();
    }
  });

  // Initial state (also after a server-side validation error re-renders the form).
  const preselected = studentSelect.value;
  if (preselected) {
    const team = teams.find((t) => t.members.some((m) => m.id === preselected));
    if (team) {
      teamSelect.value = team.id;
      renderMembers(team, preselected);
    }
  }
  checkDate();
})();
