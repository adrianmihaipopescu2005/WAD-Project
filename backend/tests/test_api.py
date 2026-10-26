from datetime import date

import pytest
from conftest import login

from app.models import ROLE_ASSISTANT, STATUS_REVOKED, Absence, ApiKey, Student, User
from app.services import validation

TUESDAY = date(2026, 10, 27)
THURSDAY = date(2026, 10, 29)
URL = "/api/v1/validate"


@pytest.fixture
def other(make_user):
    return make_user("other@example.com", ROLE_ASSISTANT)


@pytest.fixture
def student(db, assistant):
    s = Student(assistant=assistant, student_number="LM1234", first_name="Ana", last_name="Pop")
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def absence(db, student):
    """Tuesday slot: covers 2026-10-27 and 2026-11-03."""
    a = Absence(student=student, slot="TUE_18_20", start_date=TUESDAY, sessions_count=2,
                reason="Flu")
    db.session.add(a)
    db.session.commit()
    return a


@pytest.fixture
def key(app, assistant):
    return validation.generate_key(assistant)


def _get(client, key=None, **params):
    headers = {"X-API-Key": key} if key else {}
    return client.get(URL, query_string=params, headers=headers)


# --- authentication -----------------------------------------------------------------

def test_requires_key_or_login(client, absence):
    res = _get(client, student_number="LM1234", date="2026-10-27")
    assert res.status_code == 401
    assert "X-API-Key" in res.get_json()["error"]


def test_invalid_key_rejected_even_when_logged_in(client, assistant, absence):
    login(client, assistant.email)
    res = _get(client, key="lam_wrong", student_number="LM1234", date="2026-10-27")
    assert res.status_code == 401


def test_key_works_and_records_last_use(client, db, key, assistant, absence):
    res = _get(client, key=key, student_number="LM1234", date="2026-10-27")
    assert res.status_code == 200
    db.session.expire_all()
    assert db.session.get(User, assistant.id).api_key.last_used_at is not None


def test_login_session_works_without_key(client, assistant, absence):
    login(client, assistant.email)
    assert _get(client, student_number="LM1234", date="2026-10-27").get_json()["excused"] is True


def test_key_stored_hashed_only(db, key):
    stored = db.session.execute(db.select(ApiKey)).scalar_one()
    assert key.startswith("lam_")
    assert stored.key_hash != key and key not in stored.key_hash
    assert len(stored.key_hash) == 64


def test_regenerating_invalidates_old_key(client, db, assistant, key, absence):
    new_key = validation.generate_key(assistant)
    assert _get(client, key=key, student_number="LM1234", date="2026-10-27").status_code == 401
    assert _get(client, key=new_key, student_number="LM1234", date="2026-10-27").status_code == 200
    assert db.session.scalar(db.select(db.func.count(ApiKey.id))) == 1


def test_revoked_key_rejected(client, assistant, key, absence):
    validation.revoke_key(assistant)
    assert _get(client, key=key, student_number="LM1234", date="2026-10-27").status_code == 401


# --- scoping ------------------------------------------------------------------------

def test_other_assistants_student_looks_unknown(client, db, other, absence):
    other_key = validation.generate_key(other)
    res = _get(client, key=other_key, student_number="LM1234", date="2026-10-27")
    assert res.status_code == 404
    assert res.get_json() == {"error": "Student not found."}


def test_admin_key_sees_all_students(client, admin, absence):
    admin_key = validation.generate_key(admin)
    res = _get(client, key=admin_key, student_number="LM1234", date="2026-10-27")
    assert res.get_json()["excused"] is True


# --- results ------------------------------------------------------------------------

def test_excused_first_session(client, key, absence):
    data = _get(client, key=key, student_number="LM1234", date="2026-10-27").get_json()
    assert data == {
        "student_number": "LM1234", "date": "2026-10-27", "lab_day": True,
        "slot": "TUE_18_20", "slot_label": "Tuesday 18–20", "excused": True,
        "absence_id": absence.id, "until": "2026-11-03",
    }


def test_excused_second_week(client, key, absence):
    assert _get(client, key=key, student_number="LM1234", date="2026-11-03").get_json()["excused"]


@pytest.mark.parametrize("day", ["2026-11-10", "2026-10-20"])  # after the end / before the start
def test_not_excused_outside_covered_weeks(client, key, absence, day):
    data = _get(client, key=key, student_number="LM1234", date=day).get_json()
    assert data["excused"] is False and data["absence_id"] is None and data["lab_day"] is True


def test_other_slot_day_not_excused(client, key, absence):
    data = _get(client, key=key, student_number="LM1234", date=THURSDAY.isoformat()).get_json()
    assert data["slot"] == "THU_18_20" and data["excused"] is False


def test_revoked_absence_not_excused(client, db, key, absence):
    absence.status = STATUS_REVOKED
    db.session.commit()
    assert _get(client, key=key, student_number="LM1234", date="2026-10-27").get_json()["excused"] \
        is False


def test_non_lab_day(client, key, absence):
    data = _get(client, key=key, student_number="LM1234", date="2026-10-28").get_json()  # Wed
    assert data["lab_day"] is False and data["slot"] is None and data["excused"] is False


def test_student_without_absences(client, key, student):
    data = _get(client, key=key, student_number="LM1234", date="2026-10-27").get_json()
    assert data["excused"] is False


# --- bad requests -------------------------------------------------------------------

@pytest.mark.parametrize(
    ("params", "status", "message"),
    [({"date": "2026-10-27"}, 400, "student_number is required"),
     ({"student_number": "LM1234"}, 400, "YYYY-MM-DD"),
     ({"student_number": "LM1234", "date": "27.10.2026"}, 400, "YYYY-MM-DD"),
     ({"student_number": "LM1234", "date": "2026-02-30"}, 400, "YYYY-MM-DD"),
     ({"student_number": "NOPE", "date": "2026-10-27"}, 404, "Student not found")],
)
def test_bad_requests(client, key, student, params, status, message):
    res = _get(client, key=key, **params)
    assert res.status_code == status
    assert message in res.get_json()["error"]


def test_post_not_allowed(client, key):
    assert client.post(URL, headers={"X-API-Key": key}).status_code == 405


# --- API key page -------------------------------------------------------------------

def test_api_key_page_requires_login(client):
    assert "/login" in client.get("/account/api-key").headers["Location"]


def test_generate_key_shown_once(client, db, assistant):
    login(client, assistant.email)
    assert "No key" in client.get("/account/api-key").get_data(as_text=True)

    res = client.post("/account/api-key")
    assert res.headers["Cache-Control"] == "no-store"
    html = res.get_data(as_text=True)
    raw = html.split('id="new-key" value="')[1].split('"')[0]
    assert raw.startswith("lam_")
    assert _get(client, key=raw, student_number="x", date="2026-10-27").status_code == 404  # valid

    html = client.get("/account/api-key").get_data(as_text=True)
    assert raw not in html and "Active" in html


def test_revoke_key_page(client, db, assistant, key):
    login(client, assistant.email)
    client.post("/account/api-key/revoke")
    db.session.expire_all()
    assert db.session.get(User, assistant.id).api_key is None


def test_removing_assistant_deletes_key(client, db, admin, assistant, key):
    login(client, admin.email)
    client.post(f"/admin/assistants/{assistant.id}/delete")
    assert db.session.execute(db.select(ApiKey)).first() is None


# --- dashboard widget ---------------------------------------------------------------

def test_dashboard_widget_present(client, assistant):
    login(client, assistant.email)
    html = client.get("/dashboard/").get_data(as_text=True)
    assert 'id="excused-check"' in html
    assert 'data-endpoint="/api/v1/validate"' in html
    assert "js/excused-check.js" in html


@pytest.mark.parametrize(
    ("params", "expected"),
    [({"student_number": "LM1234", "date": "2026-10-27"}, 'data-result="excused"'),
     ({"student_number": "LM1234", "date": "2026-11-10"}, 'data-result="not-excused"'),
     ({"student_number": "LM1234", "date": "2026-10-28"}, 'data-result="no-lab"'),
     ({"student_number": "NOPE", "date": "2026-10-27"}, "Student not found"),
     ({"student_number": "LM1234", "date": "bad"}, "YYYY-MM-DD")],
)
def test_dashboard_widget_without_js(client, assistant, absence, params, expected):
    login(client, assistant.email)
    html = client.get("/dashboard/", query_string=params).get_data(as_text=True)
    assert expected in html


def test_dashboard_widget_scoped(client, other, absence):
    login(client, other.email)
    html = client.get(
        "/dashboard/", query_string={"student_number": "LM1234", "date": "2026-10-27"}
    ).get_data(as_text=True)
    assert "Student not found" in html
