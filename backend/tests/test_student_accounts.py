import re
import sqlite3
from datetime import timedelta

import pytest
from conftest import TUESDAY, add_student, add_team, login

from app import create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import ROLE_STUDENT, Absence, User
from app.services import student_accounts

LINK = re.compile(r"http://localhost/signup/(\S+)")


def _outbox(client):
    return client.application.extensions.get("mail_outbox", [])


def _request_link(client, email="ana@student.ro", name="Ana Pop"):
    return client.post("/signup", data={"name": name, "email": email})


def _token(client):
    return LINK.search(_outbox(client)[-1]["body"]).group(1)


def _set_password(client, token, password="newpass123"):
    return client.post(f"/signup/{token}", data={"password": password, "confirm": password})


def _absence(student, email, decision="pending", status="active", start=TUESDAY,
             reason="Doctor"):
    a = Absence(student=student, slot=student.team.slot, start_date=start, reason=reason,
                email=email, decision=decision, status=status)
    _db.session.add(a)
    _db.session.commit()
    return a


@pytest.fixture
def student_user(make_user):
    return make_user("ana@student.ro", ROLE_STUDENT)


@pytest.fixture
def as_student(client, student_user):
    login(client, student_user.email)
    return client


# --- sign up / reset by emailed link ---------------------------------------------------

def test_signup_emails_a_link_and_creates_nothing_yet(client, db):
    res = _request_link(client, email="  Ana@Student.ro ")
    assert res.status_code == 200
    assert "Check your email" in res.get_data(as_text=True)
    assert _outbox(client)[-1]["to"] == "ana@student.ro"
    assert "Create your" in _outbox(client)[-1]["subject"]
    assert db.session.execute(db.select(User)).first() is None


def test_link_creates_student_account_and_logs_in(client, db):
    _request_link(client)
    token = _token(client)
    page = client.get(f"/signup/{token}").get_data(as_text=True)
    assert "Create your account" in page and "ana@student.ro" in page

    res = _set_password(client, token)
    assert res.status_code == 302 and res.headers["Location"].endswith("/my/absences")
    user = db.session.execute(db.select(User)).scalar_one()
    assert (user.email, user.name, user.role) == ("ana@student.ro", "Ana Pop", ROLE_STUDENT)
    assert client.get("/my/absences").status_code == 200


def test_link_works_only_once(client):
    _request_link(client)
    token = _token(client)
    _set_password(client, token)
    client.post("/logout")
    res = _set_password(client, token, "attacker123")
    assert res.status_code == 400
    assert "already used" in res.get_data(as_text=True)
    assert login(client, "ana@student.ro", "newpass123").status_code == 302


def test_existing_student_gets_a_reset_link(client, student_user):
    _request_link(client)
    assert "Reset your" in _outbox(client)[-1]["subject"]
    token = _token(client)
    assert "Choose a new password" in client.get(f"/signup/{token}").get_data(as_text=True)
    _set_password(client, token)
    client.post("/logout")
    assert login(client, student_user.email).status_code == 200  # old password fails
    assert login(client, student_user.email, "newpass123").status_code == 302


def test_signup_does_not_squat_an_account(client, db):
    """Two pending links for one new email: once one is used, the other no longer works."""
    _request_link(client)
    first = _token(client)
    _request_link(client)
    second = _token(client)
    _set_password(client, second)
    assert _set_password(client, first).status_code == 400


def test_staff_email_gets_no_link_and_same_page(client, admin):
    res = _request_link(client, email=admin.email)
    assert "Check your email" in res.get_data(as_text=True)
    assert _outbox(client) == []


def test_link_for_staff_email_is_rejected(client, app, admin):
    with app.test_request_context():
        token = student_accounts._serializer().dumps(
            {"email": admin.email, "name": "x", "fp": student_accounts._fingerprint(admin)}
        )
    assert _set_password(client, token).status_code == 400
    assert login(client, admin.email).status_code == 302  # password unchanged


@pytest.mark.parametrize("token", ["garbage", "a.b.c"])
def test_bad_link(client, token):
    res = client.get(f"/signup/{token}")
    assert res.status_code == 400
    assert "not valid" in res.get_data(as_text=True)


def test_expired_link(client, monkeypatch):
    _request_link(client)
    monkeypatch.setattr(student_accounts, "LINK_MAX_AGE_SECONDS", -1)
    res = client.get(f"/signup/{_token(client)}")
    assert res.status_code == 400 and "expired" in res.get_data(as_text=True)


def test_passwords_must_match_and_be_long(client, db):
    _request_link(client)
    token = _token(client)
    res = client.post(f"/signup/{token}", data={"password": "short", "confirm": "short"})
    assert "at least 8" in res.get_data(as_text=True)
    res = client.post(f"/signup/{token}", data={"password": "longenough", "confirm": "other123"})
    assert "passwords don&#39;t match" in res.get_data(as_text=True)
    assert db.session.execute(db.select(User)).first() is None


# --- "My absences" -------------------------------------------------------------------

def test_student_login_goes_to_my_absences(client, student_user):
    res = login(client, student_user.email)
    assert res.headers["Location"].endswith("/my/absences")
    assert client.get("/login").headers["Location"].endswith("/my/absences")
    assert client.get("/signup").headers["Location"].endswith("/my/absences")


def test_sees_only_absences_reported_with_own_email(as_student, assistant):
    ana, ion = add_team(assistant, "Ana Pop", "Ion Ionescu").members
    _absence(ana, "ana@student.ro")
    _absence(ana, "other@student.ro", reason="Secret reason")  # someone reporting for Ana
    _absence(ion, "ion@student.ro")

    html = as_student.get("/my/absences").get_data(as_text=True)
    assert "Ana Pop" in html and "Pending" in html
    assert "Ion Ionescu" not in html and "Secret reason" not in html


def test_filter_by_decision_and_counts(as_student, assistant):
    ana = add_student(assistant)
    _absence(ana, "ana@student.ro", "pending")
    _absence(ana, "ana@student.ro", "motivated", start=TUESDAY + timedelta(weeks=1))
    _absence(ana, "ana@student.ro", "not_motivated", status="revoked",
             start=TUESDAY + timedelta(weeks=2))

    html = as_student.get("/my/absences").get_data(as_text=True)
    assert html.count("<tr>") == 4  # header + 3 rows, revoked included
    html = as_student.get("/my/absences?decision=motivated").get_data(as_text=True)
    assert html.count("<tr>") == 2 and "Motivated" in html
    html = as_student.get("/my/absences?decision=not_motivated").get_data(as_text=True)
    assert "No absences with this decision." in html  # the revoked one isn't counted


def test_empty_state(as_student):
    html = as_student.get("/my/absences").get_data(as_text=True)
    assert "reported any absences with this email" in html


def test_my_absences_requires_student(client, assistant):
    assert client.get("/my/absences").status_code == 302
    login(client, assistant.email)
    assert client.get("/my/absences").status_code == 403


def test_report_uses_account_email_and_shows_on_my_absences(as_student, assistant):
    s = add_student(assistant)
    html = as_student.get("/report/").get_data(as_text=True)
    assert "ana@student.ro" in html and 'name="email"' not in html
    as_student.post("/report/", data={"student_id": s.id, "start_date": TUESDAY.isoformat(),
                                      "reason": "Flu"})
    assert "Flu" in as_student.get("/my/absences").get_data(as_text=True)


def test_home_page_steps_per_role(client, as_student):
    assert 'href="/report/"' in as_student.get("/").get_data(as_text=True)
    as_student.post("/logout")
    html = client.get("/").get_data(as_text=True)
    assert "Log in to report" in html and 'href="/signup"' in html
    assert 'href="/report/"' not in html


# --- students can't reach staff features (server-side) --------------------------------

@pytest.mark.parametrize("url", [
    "/dashboard/", "/teams/", "/teams/new", "/absences/", "/absences/search.json",
    "/admin/assistants", "/account/api-key",
])
def test_student_forbidden_on_staff_pages(as_student, url):
    assert as_student.get(url).status_code == 403


def test_student_cannot_decide_or_revoke(as_student, assistant):
    a = _absence(add_student(assistant), "ana@student.ro")
    for action, data in (("decision", {"decision": "motivated"}), ("revoke", {}),
                         ("extend", {"sessions": 1})):
        assert as_student.post(f"/absences/{a.id}/{action}", data=data).status_code == 403
    _db.session.expire_all()
    assert (a.decision, a.status) == ("pending", "active")


def test_student_session_cannot_use_validation_api(as_student, assistant):
    s = add_student(assistant)
    res = as_student.get(f"/api/v1/validate?student_id={s.id}&date={TUESDAY.isoformat()}")
    assert res.status_code == 403


# --- flask upgrade-db -----------------------------------------------------------------

def test_upgrade_db_allows_students_and_keeps_data(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL, created_at DATETIME NOT NULL,
            CONSTRAINT ck_users_role CHECK (role IN ('admin', 'assistant')));
        CREATE TABLE teams (id INTEGER PRIMARY KEY,
            assistant_id INTEGER NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
            slot VARCHAR(16) NOT NULL, created_at DATETIME NOT NULL);
        INSERT INTO users VALUES (1, 'd@lab.ro', 'Darian', 'h', 'assistant', '2026-10-28');
        INSERT INTO teams VALUES (1, 1, 'TUE_18_20', '2026-10-28');
    """)
    con.close()

    class OldDb(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{path.as_posix()}"

    app = create_app(OldDb)
    runner = app.test_cli_runner()
    assert "Upgraded" in runner.invoke(args=["upgrade-db"]).output
    assert "already up to date" in runner.invoke(args=["upgrade-db"]).output

    with app.app_context():
        _db.session.add(User(email="s@x.ro", name="S", password_hash="h", role=ROLE_STUDENT))
        _db.session.commit()
        assert _db.session.get(User, 1).teams[0].slot == "TUE_18_20"
        _db.session.remove()
        _db.engine.dispose()

    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):  # the teams FK still points at users
        con.execute("DELETE FROM users WHERE id = 1")
    con.close()

