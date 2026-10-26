from datetime import date

import pytest
from conftest import login

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import (
    ROLE_ASSISTANT,
    SOURCE_PUBLIC,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    Absence,
    Student,
    User,
)

TUESDAY = date(2026, 10, 27)
THURSDAY = date(2026, 10, 29)


@pytest.fixture
def student(db, assistant):
    s = Student(assistant=assistant, student_number="LM1234", first_name="ana",
                last_name="Popescu", email="ana.popescu@student.upt.ro", study_group="2.1")
    db.session.add(s)
    db.session.commit()
    return s


def _report(**override):
    return {
        "student_number": "LM1234", "slot": "TUE_18_20", "start_date": TUESDAY.isoformat(),
        "sessions_count": 1, "reason": "Medical appointment", **override,
    }


def _absences(db):
    db.session.expire_all()
    return db.session.execute(db.select(Absence)).scalars().all()


# --- page ---------------------------------------------------------------------------

def test_report_page_is_public(client):
    res = client.get("/report/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'name="student_number"' in html
    assert "js/smart-form.js" in html


def test_report_page_offers_exactly_the_two_slots(client):
    html = client.get("/report/").get_data(as_text=True)
    options = html.split('id="slot"')[1].split("</select>")[0]
    assert options.count("<option") == 2
    assert 'value="TUE_18_20" data-weekday="2"' in options  # JS: Sunday = 0
    assert 'value="THU_18_20" data-weekday="4"' in options


def test_home_page_links_to_report(client):
    assert 'href="/report/"' in client.get("/").get_data(as_text=True)


# --- submit -------------------------------------------------------------------------

def test_submit_routes_to_the_students_assistant(client, db, student, assistant):
    res = client.post("/report/", data=_report(sessions_count=2))
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/report/thanks")

    (absence,) = _absences(db)
    assert absence.student_id == student.id
    assert absence.student.assistant_id == assistant.id
    assert absence.source == SOURCE_PUBLIC
    assert absence.status == STATUS_ACTIVE
    assert absence.sessions_count == 2

    # The assistant sees it on their dashboard pages.
    login(client, assistant.email)
    assert "Medical appointment" in client.get("/absences/").get_data(as_text=True)


def test_submit_strips_student_number(client, db, student):
    assert client.post("/report/", data=_report(student_number="  LM1234 ")).status_code == 302


def test_thanks_page_shows_summary_once_with_initials_only(client, db, student):
    client.post("/report/", data=_report(sessions_count=3))
    html = client.get("/report/thanks").get_data(as_text=True)
    assert "A. P." in html
    assert "2026-10-27" in html and "2026-11-10" in html
    assert "Popescu" not in html
    assert client.get("/report/thanks").headers["Location"].endswith("/report/")  # only once


def test_unknown_student_number_rejected(client, db, student):
    res = client.post("/report/", data=_report(student_number="NOPE"))
    assert res.status_code == 200
    assert "Student number not found" in res.get_data(as_text=True)
    assert _absences(db) == []


@pytest.mark.parametrize(
    ("slot", "day"),
    [("TUE_18_20", date(2026, 10, 26)), ("TUE_18_20", THURSDAY), ("THU_18_20", TUESDAY)],
)
def test_slot_date_mismatch_rejected(client, db, student, slot, day):
    res = client.post("/report/", data=_report(slot=slot, start_date=day.isoformat()))
    assert res.status_code == 200
    assert "is not a" in res.get_data(as_text=True)
    assert _absences(db) == []


@pytest.mark.parametrize(
    "override",
    [{"student_number": ""}, {"reason": ""}, {"sessions_count": 0}, {"sessions_count": 15},
     {"slot": "SAT_18_20"}, {"start_date": ""}],
)
def test_validation(client, db, student, override):
    res = client.post("/report/", data=_report(**override))
    assert res.status_code == 200
    assert "is-invalid" in res.get_data(as_text=True)
    assert _absences(db) == []


def test_duplicate_report_for_covered_session_rejected(client, db, student):
    client.post("/report/", data=_report(sessions_count=2))
    # The second week of the first report.
    res = client.post("/report/", data=_report(start_date="2026-11-03"))
    assert res.status_code == 200
    assert "already reported" in res.get_data(as_text=True)
    assert len(_absences(db)) == 1


def test_report_allowed_again_after_revoke(client, db, student):
    client.post("/report/", data=_report())
    (absence,) = _absences(db)
    absence.status = STATUS_REVOKED
    db.session.commit()
    assert client.post("/report/", data=_report()).status_code == 302
    assert len(_absences(db)) == 2


def test_other_slot_same_week_is_not_a_duplicate(client, db, student):
    client.post("/report/", data=_report())
    res = client.post("/report/", data=_report(slot="THU_18_20", start_date=THURSDAY.isoformat()))
    assert res.status_code == 302


def test_submitted_values_kept_after_error(client, db, student):
    html = client.post("/report/", data=_report(student_number="NOPE", reason="Keep me")) \
        .get_data(as_text=True)
    assert 'value="NOPE"' in html and "Keep me" in html


# --- lookup (smart form) ------------------------------------------------------------

def test_lookup_found_reveals_initials_and_group_only(client, student):
    data = client.get("/report/lookup.json?student_number=LM1234").get_json()
    assert data == {"found": True, "initials": "A. P.", "group": "2.1"}


def test_lookup_never_leaks_personal_data(client, student, assistant):
    raw = client.get("/report/lookup.json?student_number=LM1234").get_data(as_text=True)
    for secret in ("ana", "Popescu", "student.upt.ro", assistant.email, assistant.name):
        assert secret not in raw


@pytest.mark.parametrize("number", ["NOPE", "", "   "])
def test_lookup_not_found(client, student, number):
    assert client.get(f"/report/lookup.json?student_number={number}").get_json() == {"found": False}


def test_lookup_without_group(client, db, assistant):
    db.session.add(Student(assistant=assistant, student_number="X1", first_name="Ion",
                           last_name="Ionescu"))
    db.session.commit()
    data = client.get("/report/lookup.json?student_number=X1").get_json()
    assert data == {"found": True, "initials": "I. I.", "group": None}


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
        _db.session.add(Student(assistant=a, student_number="LM1234", first_name="A",
                                last_name="B"))
        _db.session.commit()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()


def test_report_requires_csrf_token(csrf_client):
    assert csrf_client.post("/report/", data=_report()).status_code == 400

    page = csrf_client.get("/report/").get_data(as_text=True)
    token = page.split('name="csrf_token" type="hidden" value="')[1].split('"')[0]
    assert csrf_client.post("/report/", data={**_report(), "csrf_token": token}).status_code == 302
