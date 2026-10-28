import pytest
from conftest import THURSDAY, TUESDAY, add_student, login

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import (
    MAX_SESSIONS,
    ROLE_ASSISTANT,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    Absence,
    Student,
    Team,
    User,
)

JSON = {"Accept": "application/json"}


def _absence(db, student, slot="TUE_18_20", start=TUESDAY, sessions=1, status=STATUS_ACTIVE,
             reason="Doctor", decision="pending"):
    a = Absence(
        email="s@example.com",
        student=student, slot=slot, start_date=start, sessions_count=sessions,
        status=status, reason=reason, decision=decision)
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
    return add_student(assistant, "Mine Student")


@pytest.fixture
def theirs(db, other):
    return add_student(other, "Their Student")


# --- access & scoping ---------------------------------------------------------------

@pytest.mark.parametrize("url", ["/absences/", "/absences/search.json"])
def test_anonymous_redirected(client, url):
    assert "/login" in client.get(url).headers["Location"]


def test_staff_cannot_create_absences(as_assistant):
    """Only students report absences (public form). There is no staff create page."""
    assert as_assistant.get("/absences/new").status_code == 404


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


@pytest.mark.parametrize("action", ["revoke", "extend", "decision"])
@pytest.mark.parametrize("headers", [{}, JSON])
def test_cannot_act_on_other_assistants_absence(as_assistant, db, theirs, action, headers):
    a = _absence(db, theirs)
    res = as_assistant.post(
        f"/absences/{a.id}/{action}", data={"sessions": 1, "decision": "motivated"},
        headers=headers,
    )
    assert res.status_code == 404
    if headers:
        assert "error" in res.get_json()
    a = _reload(db, a.id)
    assert a.status == STATUS_ACTIVE and a.sessions_count == 1 and a.decision == "pending"
    assert outbox(as_assistant) == []


# --- filters ------------------------------------------------------------------------

def test_filters(as_assistant, db, assistant, mine):
    second = add_student(assistant, "Ion Ionescu")
    _absence(db, mine, reason="tue-active")
    _absence(db, mine, slot="THU_18_20", start=THURSDAY, reason="thu-active", decision="motivated")
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
    html = page("decision=motivated")
    assert "thu-active" in html and "tue-active" not in html
    html = page("decision=pending")
    assert "tue-active" in html and "thu-active" not in html
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


def test_teams_search_json_scoped(as_assistant, db, mine, theirs):
    data = as_assistant.get("/teams/search.json?q=student").get_json()
    assert data["count"] == 1
    assert "Mine Student" in data["html"] and "Their Student" not in data["html"]


def test_pages_load_live_search_script(as_assistant):
    for url in ("/absences/", "/teams/"):
        html = as_assistant.get(url).get_data(as_text=True)
        assert "js/live-search.js" in html
        assert "data-live-search" in html


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
    assert mine.name in data["html"]  # student column kept for the list page
    assert "revoked" in data["message"]


def test_revoke_json_without_student_column(as_assistant, db, mine):
    a = _absence(db, mine)
    data = as_assistant.post(
        f"/absences/{a.id}/revoke", data={"show_student": "0"}, headers=JSON
    ).get_json()
    assert "Mine Student" not in data["html"]


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


# --- decision (motivated / not motivated) + email -----------------------------------

def outbox(client):
    return client.application.extensions.get("mail_outbox", [])


def _decide(client, absence, decision, **extra):
    return client.post(f"/absences/{absence.id}/decision",
                       data={"decision": decision, **extra}, headers=JSON)


def test_new_absence_is_pending_with_buttons(as_assistant, db, mine):
    _absence(db, mine)
    html = as_assistant.get("/absences/").get_data(as_text=True)
    assert 'data-decision="pending"' in html and ">Pending<" in html
    assert 'name="decision" value="motivated"' in html
    assert 'name="decision" value="not_motivated"' in html
    assert "s@example.com" in html  # staff see where the email goes


def test_mark_motivated_emails_the_student(as_assistant, db, mine, assistant):
    a = _absence(db, mine)
    res = _decide(as_assistant, a, "motivated")
    assert res.status_code == 200
    data = res.get_json()
    assert data["absence"]["decision"] == "motivated" and data["category"] == "success"
    assert 'data-decision="motivated"' in data["html"] and "Emailed" in data["html"]
    assert "Email sent to s@example.com" in data["message"]

    (mail,) = outbox(as_assistant)
    assert mail["to"] == "s@example.com"
    assert mail["subject"] == "Your lab absence on 2026-10-27 was motivated"
    assert "Hi Mine Student" in mail["body"] and "MOTIVATED" in mail["body"]
    assert "Tuesday 27 October 2026" in mail["body"] and assistant.name in mail["body"]
    assert "You are excused" in mail["body"] and "Doctor" in mail["body"]

    a = _reload(db, a.id)
    assert a.motivated and a.decided_at is not None and a.notified_at is not None


def test_mark_not_motivated_emails_the_student(as_assistant, db, mine):
    a = _absence(db, mine)
    _decide(as_assistant, a, "not_motivated")
    (mail,) = outbox(as_assistant)
    assert mail["subject"].endswith("was not motivated")
    assert "NOT MOTIVATED" in mail["body"] and "not excused" in mail["body"]
    assert _reload(db, a.id).decision == "not_motivated"


def test_changing_the_decision_sends_a_new_email(as_assistant, db, mine):
    a = _absence(db, mine)
    _decide(as_assistant, a, "not_motivated")
    _decide(as_assistant, a, "motivated")
    first, second = outbox(as_assistant)
    assert first["subject"].endswith("was not motivated")
    assert second["subject"].endswith("was motivated")
    assert _reload(db, a.id).motivated


def test_failed_email_keeps_the_decision_and_warns(as_assistant, db, mine, monkeypatch):
    from app.services import mail

    monkeypatch.setattr(mail, "send", lambda *args: False)
    a = _absence(db, mine)
    data = _decide(as_assistant, a, "motivated").get_json()
    assert data["category"] == "warning" and "couldn't be sent" in data["message"]
    assert "Not emailed" in data["html"]
    a = _reload(db, a.id)
    assert a.motivated and a.notified_at is None

    monkeypatch.undo()  # retry: click the same button again
    _decide(as_assistant, a, "motivated")
    assert _reload(db, a.id).notified_at is not None


def test_decision_without_js(as_assistant, db, mine):
    a = _absence(db, mine)
    res = as_assistant.post(f"/absences/{a.id}/decision",
                            data={"decision": "motivated", "next": f"/students/{mine.id}"})
    assert res.headers["Location"].endswith(f"/students/{mine.id}")
    assert _reload(db, a.id).motivated


@pytest.mark.parametrize("decision", ["", "pending", "maybe"])
def test_invalid_decision(as_assistant, db, mine, decision):
    a = _absence(db, mine)
    assert _decide(as_assistant, a, decision).status_code == 400
    assert _reload(db, a.id).decision == "pending" and outbox(as_assistant) == []


def test_revoked_cannot_be_decided(as_assistant, db, mine):
    a = _absence(db, mine, status=STATUS_REVOKED)
    assert _decide(as_assistant, a, "motivated").status_code == 409
    assert _reload(db, a.id).decision == "pending" and outbox(as_assistant) == []


def test_admin_decides_any_absence(as_admin, db, theirs):
    a = _absence(db, theirs)
    assert _decide(as_admin, a, "motivated").status_code == 200
    assert _reload(db, a.id).motivated


def test_mail_not_configured_fails_softly(app, db, mine):
    from app.services import mail

    app.config.update(MAIL_SUPPRESS=False, MAIL_USERNAME=None)
    with app.test_request_context():
        assert mail.send("s@example.com", "subject", "body") is False


def test_mail_server_error_fails_softly(app, monkeypatch):
    import smtplib

    from app.services import mail

    def refuse(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    app.config.update(MAIL_SUPPRESS=False, MAIL_USERNAME="lab@gmail.com", MAIL_PASSWORD="x")
    with app.test_request_context():
        assert mail.send("s@example.com", "subject", "body") is False


# --- profile ------------------------------------------------------------------------

def test_profile_has_actions(as_assistant, db, mine):
    _absence(db, mine)
    html = as_assistant.get(f"/students/{mine.id}").get_data(as_text=True)
    assert "/absences/new" not in html
    assert f"/absences/{mine.absences[0].id}/decision" in html
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
        student = Student(name="A B")
        _db.session.add(Team(assistant=assistant, slot="TUE_18_20", members=[student]))
        _db.session.add(_absence_obj := Absence(email="s@example.com", 
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
