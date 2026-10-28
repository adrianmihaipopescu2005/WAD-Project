from datetime import date

import pytest
from conftest import THURSDAY, TUESDAY, add_team, login

from app import clock, create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import ROLE_ASSISTANT, STATUS_ACTIVE, STATUS_REVOKED, Absence, Student, Team, User


@pytest.fixture
def team(db, assistant):
    return add_team(assistant, "Ana Popescu", "Ion Ionescu")


@pytest.fixture
def student(team):
    return team.members[0]


@pytest.fixture
def thu_student(assistant):
    return add_team(assistant, "Dan Stan", slot="THU_18_20").members[0]


def _report(student, **override):
    return {
        "student_id": student.id, "start_date": TUESDAY.isoformat(),
        "reason": "Medical appointment", **override,
    }


def _absences(db):
    db.session.expire_all()
    return db.session.execute(db.select(Absence)).scalars().all()


def _errors(res):
    return res.get_data(as_text=True)


# --- page ---------------------------------------------------------------------------

def test_report_page_is_public_and_groups_names_by_team(client, team, thu_student):
    res = client.get("/report/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'name="student_id"' in html
    assert "js/smart-form.js" in html
    assert 'label="Tuesday: Ana Popescu &amp; Ion Ionescu"' in html
    assert 'data-weekday="2"' in html and 'data-weekday="4"' in html  # JS: Sunday = 0
    # Tuesday teams come first.
    assert html.index("Ana Popescu") < html.index("Dan Stan")
    assert 'name="student_number"' not in html and 'name="slot"' not in html


def test_report_page_without_teams(client):
    assert "No teams have been added yet" in client.get("/report/").get_data(as_text=True)


def test_date_picker_starts_tomorrow(client, team):
    html = client.get("/report/").get_data(as_text=True)
    assert 'min="2026-10-27"' in html  # today is Monday 2026-10-26


def test_home_page_links_to_report(client):
    assert 'href="/report/"' in client.get("/").get_data(as_text=True)


# --- submit -------------------------------------------------------------------------

def test_submit_goes_to_the_teams_assistant(client, db, student, assistant):
    res = client.post("/report/", data=_report(student))
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/report/thanks")

    (absence,) = _absences(db)
    assert absence.student_id == student.id
    assert absence.slot == "TUE_18_20"  # from the team, not from the form
    assert absence.status == STATUS_ACTIVE
    assert absence.sessions_count == 1
    assert not absence.motivated  # staff tick it after checking

    login(client, assistant.email)
    assert "Medical appointment" in client.get("/absences/").get_data(as_text=True)


def test_teammate_reports_separately(client, db, team):
    ana, ion = team.members
    client.post("/report/", data=_report(ion))
    (absence,) = _absences(db)
    assert absence.student_id == ion.id


def test_thanks_page_shows_summary_once(client, db, student):
    client.post("/report/", data=_report(student))
    html = client.get("/report/thanks").get_data(as_text=True)
    assert "Ana Popescu" in html and "Tuesday 18–20" in html and "2026-10-27" in html
    assert client.get("/report/thanks").headers["Location"].endswith("/report/")  # only once


@pytest.mark.parametrize("student_id", ["", "999", "abc"])
def test_unknown_student_rejected(client, db, student, student_id):
    res = client.post("/report/", data=_report(student, student_id=student_id))
    assert res.status_code == 200
    assert "Choose your team and your name." in _errors(res)
    assert _absences(db) == []


def test_wrong_weekday_for_team_rejected(client, db, student, thu_student):
    res = client.post("/report/", data=_report(student, start_date=THURSDAY.isoformat()))
    assert "is not a Tuesday" in _errors(res)
    res = client.post("/report/", data=_report(thu_student, start_date=TUESDAY.isoformat()))
    assert "is not a Thursday" in _errors(res)
    assert _absences(db) == []


# --- deadline: until 23:59 the day before -----------------------------------------------

def test_tuesday_can_be_reported_on_monday(client, db, student):
    # conftest pins today to Monday 2026-10-26.
    assert client.post("/report/", data=_report(student)).status_code == 302


def test_tuesday_cannot_be_reported_on_the_day(client, db, student, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: TUESDAY)
    res = client.post("/report/", data=_report(student))
    assert res.status_code == 200
    assert "Too late" in _errors(res) and "Monday for Tuesday" in _errors(res)
    assert _absences(db) == []


def test_thursday_deadline_is_wednesday(client, db, thu_student, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 28))  # Wednesday
    assert client.post("/report/", data=_report(
        thu_student, start_date=THURSDAY.isoformat())).status_code == 302
    monkeypatch.setattr(clock, "today", lambda: THURSDAY)
    res = client.post("/report/", data=_report(
        thu_student, start_date="2026-10-29", reason="again"))
    assert "Wednesday for Thursday" in _errors(res)


def test_past_session_rejected(client, db, student):
    res = client.post("/report/", data=_report(student, start_date="2026-10-20"))
    assert "Too late" in _errors(res)


def test_too_far_ahead_rejected(client, db, student):
    res = client.post("/report/", data=_report(student, start_date="2027-06-01"))
    assert "about 6 months ahead" in _errors(res)


def test_clock_uses_romanian_time():
    assert str(clock.TIMEZONE) == "Europe/Bucharest"


@pytest.mark.parametrize("override", [{"reason": ""}, {"start_date": ""}, {"start_date": "x"}])
def test_validation(client, db, student, override):
    res = client.post("/report/", data=_report(student, **override))
    assert res.status_code == 200
    assert "is-invalid" in res.get_data(as_text=True)
    assert _absences(db) == []


def test_duplicate_report_rejected(client, db, student):
    client.post("/report/", data=_report(student))
    res = client.post("/report/", data=_report(student, reason="again"))
    assert res.status_code == 200
    assert "already reported" in _errors(res)
    assert len(_absences(db)) == 1


def test_session_covered_by_extended_absence_is_duplicate(client, db, student):
    client.post("/report/", data=_report(student))
    (absence,) = _absences(db)
    absence.sessions_count = 2  # staff extended it to next Tuesday
    db.session.commit()
    res = client.post("/report/", data=_report(student, start_date="2026-11-03"))
    assert "already reported" in _errors(res)


def test_report_allowed_again_after_revoke(client, db, student):
    client.post("/report/", data=_report(student))
    (absence,) = _absences(db)
    absence.status = STATUS_REVOKED
    db.session.commit()
    assert client.post("/report/", data=_report(student)).status_code == 302
    assert len(_absences(db)) == 2


def test_submitted_values_kept_after_error(client, db, student):
    html = client.post("/report/", data=_report(student, start_date="2026-10-29",
                                                reason="Keep me")).get_data(as_text=True)
    assert f'<option value="{student.id}" selected>' in html and "Keep me" in html


def test_lookup_endpoint_removed(client):
    assert client.get("/report/lookup.json?student_number=X").status_code == 404


# --- CSRF ---------------------------------------------------------------------------

class CsrfConfig(TestingConfig):
    WTF_CSRF_ENABLED = True


@pytest.fixture
def csrf_client():
    app = create_app(CsrfConfig)
    with app.app_context():
        a = User(email="a@example.com", name="A", role=ROLE_ASSISTANT)
        a.set_password("pw")
        _db.create_all()
        _db.session.add(Team(assistant=a, slot="TUE_18_20", members=[Student(name="A B")]))
        _db.session.commit()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()


def test_report_requires_csrf_token(csrf_client):
    data = {"student_id": 1, "start_date": TUESDAY.isoformat(), "reason": "x"}
    assert csrf_client.post("/report/", data=data).status_code == 400

    page = csrf_client.get("/report/").get_data(as_text=True)
    token = page.split('name="csrf_token" type="hidden" value="')[1].split('"')[0]
    assert csrf_client.post("/report/", data={**data, "csrf_token": token}).status_code == 302
