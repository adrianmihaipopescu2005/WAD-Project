from datetime import date

import pytest
from conftest import login

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import (
    MAX_SESSIONS,
    ROLE_ASSISTANT,
    SOURCE_ASSISTANT,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    Absence,
    Student,
    User,
)

TUESDAY = date(2026, 10, 27)
THURSDAY = date(2026, 10, 29)
JSON = {"Accept": "application/json"}


def _student(db, assistant, number, first="Ana", last="Pop"):
    s = Student(assistant=assistant, student_number=number, first_name=first, last_name=last)
    db.session.add(s)
    db.session.commit()
    return s


def _absence(db, student, slot="TUE_18_20", start=TUESDAY, sessions=1, status=STATUS_ACTIVE,
             reason="Doctor"):
    a = Absence(student=student, slot=slot, start_date=start, sessions_count=sessions,
                status=status, reason=reason)
    db.session.add(a)
    db.session.commit()
    return a


def _reload(db, id_):
    db.session.expire_all()
    return db.session.get(Absence, id_)


@pytest.fixture
def other(make_user):
    return make_user("other@example.com", ROLE_ASSISTANT)


@pytest.fixture
def as_assistant(client, assistant):
    login(client, assistant.email)
    return client


@pytest.fixture
def as_admin(client, admin):
    login(client, admin.email)
    return client


@pytest.fixture
def mine(db, assistant):
    return _student(db, assistant, "MINE1", "Mine", "Student")


@pytest.fixture
def theirs(db, other):
    return _student(db, other, "THEIRS1", "Their", "Student")


def _new(student, **override):
    return {
        "student_id": student.id, "slot": "TUE_18_20", "start_date": TUESDAY.isoformat(),
        "sessions_count": 1, "reason": "Medical appointment", **override,
    }


# --- access & scoping ---------------------------------------------------------------

@pytest.mark.parametrize("url", ["/absences/", "/absences/new", "/absences/search.json"])
def test_anonymous_redirected(client, url):
    assert "/login" in client.get(url).headers["Location"]


def test_list_scoped_to_own_students(as_assistant, db, mine, theirs):
    _absence(db, mine, reason="mine-reason")
    _absence(db, theirs, reason="their-reason")
    html = as_assistant.get("/absences/").get_data(as_text=True)
    assert "mine-reason" in html
    assert "their-reason" not in html


def test_admin_sees_all_and_filters_by_assistant(as_admin, db, mine, theirs, other):
    _absence(db, mine, reason="mine-reason")
    _absence(db, theirs, reason="their-reason")
    html = as_admin.get("/absences/").get_data(as_text=True)
    assert "mine-reason" in html and "their-reason" in html
    html = as_admin.get(f"/absences/?assistant={other.id}").get_data(as_text=True)
    assert "their-reason" in html and "mine-reason" not in html


def test_assistant_assistant_filter_is_ignored(as_assistant, db, mine, theirs, other):
    _absence(db, theirs, reason="their-reason")
    html = as_assistant.get(f"/absences/?assistant={other.id}").get_data(as_text=True)
    assert "their-reason" not in html


@pytest.mark.parametrize("action", ["revoke", "extend"])
@pytest.mark.parametrize("headers", [{}, JSON])
def test_cannot_act_on_other_assistants_absence(as_assistant, db, theirs, action, headers):
    a = _absence(db, theirs)
    res = as_assistant.post(f"/absences/{a.id}/{action}", data={"sessions": 1}, headers=headers)
    assert res.status_code == 404
    if headers:
        assert "error" in res.get_json()
    a = _reload(db, a.id)
    assert a.status == STATUS_ACTIVE and a.sessions_count == 1


def test_cannot_create_for_other_assistants_student(as_assistant, db, mine, theirs):
    res = as_assistant.post("/absences/new", data=_new(theirs))
    assert res.status_code == 200  # not a valid choice for this assistant
    assert db.session.execute(db.select(Absence)).first() is None


# --- filters ------------------------------------------------------------------------

def test_filters(as_assistant, db, assistant, mine):
    second = _student(db, assistant, "S2", "Ion", "Ionescu")
    _absence(db, mine, reason="tue-active")
    _absence(db, mine, slot="THU_18_20", start=THURSDAY, reason="thu-active")
    _absence(db, second, status=STATUS_REVOKED, reason="ion-revoked")

    def page(qs):
        return as_assistant.get(f"/absences/?{qs}").get_data(as_text=True)

    html = page(f"student={second.id}")
    assert "ion-revoked" in html and "tue-active" not in html
    html = page("status=revoked")
    assert "ion-revoked" in html and "tue-active" not in html
    html = page("slot=THU_18_20")
    assert "thu-active" in html and "tue-active" not in html
    html = page("q=ionescu")
    assert "ion-revoked" in html and "thu-active" not in html
    assert "No absences match" in page("q=zzz")


def test_empty_state(as_assistant):
    assert "No absences yet" in as_assistant.get("/absences/").get_data(as_text=True)


# --- live search (JSON) -------------------------------------------------------------

def test_search_json_returns_count_and_rendered_rows(as_assistant, db, mine, theirs):
    _absence(db, mine, reason="mine-reason")
    _absence(db, theirs, reason="their-reason")
    data = as_assistant.get("/absences/search.json?q=mine").get_json()
    assert data["count"] == 1
    assert "mine-reason" in data["html"] and "their-reason" not in data["html"]
    assert "<html" not in data["html"]  # a fragment, not a whole page


def test_search_json_empty(as_assistant, db, mine):
    _absence(db, mine)
    data = as_assistant.get("/absences/search.json?q=nobody").get_json()
    assert data["count"] == 0
    assert "No absences match" in data["html"]


def test_search_json_escapes_user_content(as_assistant, db, mine):
    _absence(db, mine, reason="<script>alert(1)</script>")
    html = as_assistant.get("/absences/search.json").get_json()["html"]
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_students_search_json_scoped(as_assistant, db, mine, theirs):
    data = as_assistant.get("/students/search.json?q=student").get_json()
    assert data["count"] == 1
    assert "MINE1" in data["html"] and "THEIRS1" not in data["html"]


def test_pages_load_live_search_script(as_assistant):
    for url in ("/absences/", "/students/"):
        html = as_assistant.get(url).get_data(as_text=True)
        assert "js/live-search.js" in html
        assert "data-live-search" in html


# --- create -------------------------------------------------------------------------

def test_create_absence(as_assistant, db, mine):
    res = as_assistant.post("/absences/new", data=_new(mine, sessions_count=2))
    assert res.status_code == 302
    assert res.headers["Location"].endswith(f"/students/{mine.id}")
    a = db.session.execute(db.select(Absence)).scalar_one()
    assert (a.slot, a.start_date, a.sessions_count) == ("TUE_18_20", TUESDAY, 2)
    assert a.source == SOURCE_ASSISTANT and a.status == STATUS_ACTIVE


def test_create_preselects_student(as_assistant, db, assistant, mine):
    second = _student(db, assistant, "S2")
    html = as_assistant.get(f"/absences/new?student_id={second.id}").get_data(as_text=True)
    assert f'<option selected value="{second.id}">' in html


def test_create_without_students_redirects(as_assistant):
    assert as_assistant.get("/absences/new").headers["Location"].endswith("/students/new")


@pytest.mark.parametrize(
    ("slot", "day"),
    [("TUE_18_20", date(2026, 10, 26)), ("TUE_18_20", THURSDAY), ("THU_18_20", TUESDAY)],
)
def test_create_slot_date_mismatch_is_form_error(as_assistant, db, mine, slot, day):
    res = as_assistant.post("/absences/new", data=_new(mine, slot=slot, start_date=day.isoformat()))
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "is not a" in html and "is-invalid" in html
    assert db.session.execute(db.select(Absence)).first() is None


@pytest.mark.parametrize(
    "override",
    [{"sessions_count": 0}, {"sessions_count": MAX_SESSIONS + 1}, {"reason": ""},
     {"start_date": "not-a-date"}, {"slot": "FRI_18_20"}],
)
def test_create_validation(as_assistant, db, mine, override):
    res = as_assistant.post("/absences/new", data=_new(mine, **override))
    assert res.status_code == 200
    assert "is-invalid" in res.get_data(as_text=True)
    assert db.session.execute(db.select(Absence)).first() is None


def test_admin_creates_for_any_student(as_admin, db, theirs):
    assert as_admin.post("/absences/new", data=_new(theirs)).status_code == 302


# --- revoke -------------------------------------------------------------------------

def test_revoke_without_js_redirects_back_and_keeps_row(as_assistant, db, mine):
    a = _absence(db, mine)
    res = as_assistant.post(f"/absences/{a.id}/revoke", data={"next": f"/students/{mine.id}"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith(f"/students/{mine.id}")
    a = _reload(db, a.id)
    assert a is not None and a.status == STATUS_REVOKED and a.revoked_at is not None


def test_revoke_json_returns_updated_row(as_assistant, db, mine):
    a = _absence(db, mine)
    res = as_assistant.post(
        f"/absences/{a.id}/revoke", data={"show_student": "1"}, headers=JSON
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["absence"]["status"] == STATUS_REVOKED
    assert f'id="absence-{a.id}"' in data["html"]
    assert 'data-status="revoked"' in data["html"]
    assert "Revoke</button>" not in data["html"]
    assert mine.full_name in data["html"]  # student column kept for the list page
    assert "revoked" in data["message"]


def test_revoke_json_without_student_column(as_assistant, db, mine):
    a = _absence(db, mine)
    data = as_assistant.post(
        f"/absences/{a.id}/revoke", data={"show_student": "0"}, headers=JSON
    ).get_json()
    assert "MINE1" not in data["html"]


def test_revoke_twice_conflicts(as_assistant, db, mine):
    a = _absence(db, mine, status=STATUS_REVOKED)
    res = as_assistant.post(f"/absences/{a.id}/revoke", headers=JSON)
    assert res.status_code == 409
    assert "already revoked" in res.get_json()["error"]


def test_revoke_ignores_unsafe_next(as_assistant, db, mine):
    a = _absence(db, mine)
    res = as_assistant.post(f"/absences/{a.id}/revoke", data={"next": "https://evil.com"})
    assert res.headers["Location"].endswith("/absences/")


def test_revoke_requires_post(as_assistant, db, mine):
    a = _absence(db, mine)
    assert as_assistant.get(f"/absences/{a.id}/revoke").status_code == 405


# --- extend -------------------------------------------------------------------------

def test_extend_json(as_assistant, db, mine):
    a = _absence(db, mine, sessions=1)
    res = as_assistant.post(f"/absences/{a.id}/extend", data={"sessions": 2}, headers=JSON)
    assert res.status_code == 200
    data = res.get_json()
    assert data["absence"]["sessions_count"] == 3
    assert data["absence"]["end_date"] == "2026-11-10"
    assert 'data-field="sessions">3<' in data["html"]
    assert _reload(db, a.id).sessions_count == 3


def test_extend_without_js(as_assistant, db, mine):
    a = _absence(db, mine)
    res = as_assistant.post(f"/absences/{a.id}/extend", data={"sessions": 1}, follow_redirects=True)
    assert "extended to 2 session(s)" in res.get_data(as_text=True)


def test_extend_revoked_conflicts(as_assistant, db, mine):
    a = _absence(db, mine, status=STATUS_REVOKED)
    res = as_assistant.post(f"/absences/{a.id}/extend", data={"sessions": 1}, headers=JSON)
    assert res.status_code == 409
    assert _reload(db, a.id).sessions_count == 1


@pytest.mark.parametrize("sessions", ["0", "-1", "abc", ""])
def test_extend_invalid_amount(as_assistant, db, mine, sessions):
    a = _absence(db, mine)
    res = as_assistant.post(f"/absences/{a.id}/extend", data={"sessions": sessions}, headers=JSON)
    assert res.status_code == 400
    assert _reload(db, a.id).sessions_count == 1


def test_extend_capped_at_max(as_assistant, db, mine):
    a = _absence(db, mine, sessions=MAX_SESSIONS - 1)
    ok = as_assistant.post(f"/absences/{a.id}/extend", data={"sessions": 1}, headers=JSON)
    assert ok.status_code == 200
    assert "disabled" in ok.get_json()["html"]  # nothing more to add
    res = as_assistant.post(f"/absences/{a.id}/extend", data={"sessions": 1}, headers=JSON)
    assert res.status_code == 400
    assert _reload(db, a.id).sessions_count == MAX_SESSIONS


# --- profile ------------------------------------------------------------------------

def test_profile_has_add_button_and_actions(as_assistant, db, mine):
    _absence(db, mine)
    html = as_assistant.get(f"/students/{mine.id}").get_data(as_text=True)
    assert f"/absences/new?student_id={mine.id}" in html
    assert "js/absence-actions.js" in html
    assert "js-absence-action" in html
    assert f'name="next" value="/students/{mine.id}"' in html


def test_navbar_has_absences_link(as_assistant):
    assert 'href="/absences/"' in as_assistant.get("/dashboard/").get_data(as_text=True)


# --- CSRF ---------------------------------------------------------------------------

class CsrfConfig(TestingConfig):
    WTF_CSRF_ENABLED = True


@pytest.fixture
def csrf_app():
    app = create_app(CsrfConfig)
    with app.app_context():
        _db.create_all()
        assistant = User(email="a@example.com", name="A", role=ROLE_ASSISTANT)
        assistant.set_password("pw")
        student = Student(assistant=assistant, student_number="S1", first_name="A", last_name="B")
        _db.session.add(_absence_obj := Absence(
            student=student, slot="TUE_18_20", start_date=TUESDAY, reason="x"
        ))
        _db.session.commit()
        yield app, _absence_obj.id
        _db.session.remove()
        _db.drop_all()


def _csrf_from_meta(html):
    return html.split('name="csrf-token" content="')[1].split('"')[0]


def test_fetch_post_needs_csrf_header(csrf_app):
    app, absence_id = csrf_app
    client = app.test_client()
    page = client.get("/login").get_data(as_text=True)
    client.post("/login", data={
        "email": "a@example.com", "password": "pw", "csrf_token": _csrf_from_meta(page),
    })

    res = client.post(f"/absences/{absence_id}/revoke", headers=JSON)
    assert res.status_code == 400
    assert "error" in res.get_json()  # JSON error, not an HTML page

    token = _csrf_from_meta(client.get("/absences/").get_data(as_text=True))
    res = client.post(
        f"/absences/{absence_id}/revoke", headers={**JSON, "X-CSRFToken": token}
    )
    assert res.status_code == 200
    assert res.get_json()["absence"]["status"] == STATUS_REVOKED
