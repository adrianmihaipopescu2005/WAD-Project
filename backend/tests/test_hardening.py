"""Fixes from the final review (M8): date window, overlap, rate limits, error shapes, races."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import TODAY, login
from sqlalchemy.exc import IntegrityError

from app import create_app, ratelimit
from app.config import Config, TestingConfig
from app.extensions import db as _db
from app.models import Absence, ApiKey, Student
from app.services import students as students_service
from app.services import validation

NEXT_TUESDAY = TODAY + timedelta(days=1)  # 2026-10-27


@pytest.fixture
def student(db, assistant):
    s = Student(assistant=assistant, student_number="LM1234", first_name="Ana", last_name="Pop")
    db.session.add(s)
    db.session.commit()
    return s


def _report(**override):
    return {
        "student_number": "LM1234", "slot": "TUE_18_20",
        "start_date": NEXT_TUESDAY.isoformat(), "sessions_count": 1, "reason": "x", **override,
    }


def _count(db, model):
    return db.session.scalar(db.select(db.func.count(model.id)))


# --- date window (30 days back, ~6 months ahead) -------------------------------------

@pytest.mark.parametrize(
    ("day", "ok"),
    [("2026-09-29", True),    # Tuesday, 27 days back
     ("2026-09-22", False),   # Tuesday, 34 days back
     ("2027-04-27", True),    # Tuesday, 183 days ahead
     ("2027-05-04", False),   # Tuesday, 190 days ahead
     ("9999-12-28", False)],  # the overflow case from the review
)
def test_public_date_window(client, db, student, day, ok):
    res = client.post("/report/", data=_report(start_date=day))
    assert (res.status_code == 302) is ok
    if not ok:
        assert "Pick a date between" in res.get_data(as_text=True)
        assert _count(db, Absence) == 0


def test_staff_form_has_same_window(client, db, assistant, student):
    login(client, assistant.email)
    res = client.post("/absences/new", data={
        "student_id": student.id, "slot": "TUE_18_20", "start_date": "9999-12-28",
        "sessions_count": 14, "reason": "x",
    })
    assert res.status_code == 200
    assert "Pick a date between" in res.get_data(as_text=True)
    assert _count(db, Absence) == 0


# --- public overlap and generic duplicate message ------------------------------------

def test_overlap_checked_across_the_whole_new_range(client, db, student):
    # Existing absence: 2026-11-03 only. The new report starts a week earlier, for 2 sessions.
    db.session.add(Absence(student=student, slot="TUE_18_20", start_date=NEXT_TUESDAY
                           + timedelta(weeks=1), reason="x"))
    db.session.commit()
    res = client.post("/report/", data=_report(sessions_count=2))
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "couldn" in html and "absent" not in html.lower().split("<main")[1].split("</main>")[0]
    assert _count(db, Absence) == 1


def test_unknown_number_uses_adr_wording(client, student):
    html = client.post("/report/", data=_report(student_number="NOPE")).get_data(as_text=True)
    assert "Student number not found, contact your lab assistant." in html


# --- rate limits ----------------------------------------------------------------------

class LimitedConfig(TestingConfig):
    RATELIMIT_ENABLED = True


@pytest.fixture
def limited_client():
    ratelimit.reset()
    app = create_app(LimitedConfig)
    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()
    ratelimit.reset()


def test_lookup_rate_limited(limited_client):
    for _ in range(30):
        assert limited_client.get("/report/lookup.json?student_number=X").status_code == 200
    res = limited_client.get("/report/lookup.json?student_number=X")
    assert res.status_code == 429
    assert "Too many requests" in res.get_data(as_text=True)


def test_report_posts_rate_limited_but_page_still_loads(limited_client):
    for _ in range(10):
        limited_client.post("/report/", data=_report())
    res = limited_client.post("/report/", data=_report())
    assert res.status_code == 429
    assert "Too many requests" in res.get_data(as_text=True)  # HTML error page
    assert limited_client.get("/report/").status_code == 200  # GETs aren't counted


def test_rate_limit_json_for_fetch(limited_client):
    for _ in range(30):
        limited_client.get("/report/lookup.json?student_number=X")
    res = limited_client.get(
        "/report/lookup.json?student_number=X", headers={"Accept": "application/json"}
    )
    assert res.status_code == 429 and "error" in res.get_json()


def test_rate_limit_window_slides(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: now[0])
    ratelimit.reset()
    assert all(ratelimit._allowed("k", 2, 60) for _ in range(2))
    assert not ratelimit._allowed("k", 2, 60)
    now[0] += 61
    assert ratelimit._allowed("k", 2, 60)
    ratelimit.reset()


# --- error shapes ---------------------------------------------------------------------

def test_api_405_is_json_without_accept_header(client):
    res = client.post("/api/v1/validate")
    assert res.status_code == 405
    assert "error" in res.get_json()


def test_expired_session_fetch_gets_json_401(client):
    res = client.get("/absences/search.json", headers={"Accept": "application/json"})
    assert res.status_code == 401
    assert "session" in res.get_json()["error"]


def test_html_400_uses_error_page(app):
    class Csrf(TestingConfig):
        WTF_CSRF_ENABLED = True

    csrf_app = create_app(Csrf)
    with csrf_app.app_context():
        res = csrf_app.test_client().post("/report/", data=_report())
        assert res.status_code == 400
        assert "Bad request" in res.get_data(as_text=True)


@pytest.mark.parametrize("value", ["20261027", "2026-W44-2", "2026-10-27T10:00", " "])
def test_parse_day_only_accepts_yyyy_mm_dd(value):
    with pytest.raises(validation.ValidationError):
        validation.parse_day(value)


def test_parse_day_ok():
    assert validation.parse_day(" 2026-10-27 ") == NEXT_TUESDAY


# --- races and rollbacks --------------------------------------------------------------

def test_duplicate_student_number_race_is_a_form_error(client, db, assistant, student,
                                                       monkeypatch):
    # Simulate the race: the pre-check passes, but the UNIQUE constraint fires on commit.
    monkeypatch.setattr(students_service, "_number_taken", lambda *a, **k: False)
    login(client, assistant.email)
    res = client.post("/students/new", data={
        "student_number": "LM1234", "first_name": "B", "last_name": "C",
    })
    assert res.status_code == 200
    assert "already exists" in res.get_data(as_text=True)
    assert _count(db, Student) == 1
    assert client.get("/students/").status_code == 200  # session still usable


def test_generate_key_rolls_back_and_keeps_old_key(db, assistant, monkeypatch):
    old = validation.generate_key(assistant)

    def boom():
        raise IntegrityError("x", {}, Exception())

    monkeypatch.setattr(db.session, "commit", boom)
    with pytest.raises(IntegrityError):
        validation.generate_key(assistant)
    monkeypatch.undo()
    assert validation.user_for_key(old) is not None
    assert _count(db, ApiKey) == 1


def test_last_used_written_at_most_once_a_minute(db, assistant):
    raw = validation.generate_key(assistant)
    validation.user_for_key(raw)
    first = db.session.execute(db.select(ApiKey)).scalar_one().last_used_at
    validation.user_for_key(raw)
    assert db.session.execute(db.select(ApiKey)).scalar_one().last_used_at == first

    key = db.session.execute(db.select(ApiKey)).scalar_one()
    key.last_used_at = datetime.now(UTC) - timedelta(minutes=2)
    db.session.commit()
    validation.user_for_key(raw)
    assert db.session.execute(db.select(ApiKey)).scalar_one().last_used_at.replace(
        tzinfo=UTC) > datetime.now(UTC) - timedelta(seconds=30)


# --- search & login -------------------------------------------------------------------

def test_search_wildcards_match_literally(client, db, assistant, make_user):
    db.session.add_all([
        Student(assistant=assistant, student_number="A_1", first_name="X", last_name="Y"),
        Student(assistant=assistant, student_number="AB1", first_name="X", last_name="Y"),
    ])
    db.session.commit()
    login(client, assistant.email)
    data = client.get("/students/search.json?q=A_1").get_json()
    assert data["count"] == 1 and "A_1" in data["html"]
    assert client.get("/students/search.json?q=%25").get_json()["count"] == 0


def test_unknown_email_still_checks_a_hash(client, monkeypatch):
    from app.services import auth

    calls = []
    real = auth.check_password_hash
    monkeypatch.setattr(auth, "check_password_hash", lambda h, p: calls.append(h) or real(h, p))
    client.post("/login", data={"email": "nobody@example.com", "password": "x"})
    assert calls == [auth._DUMMY_HASH]


# --- secret key -----------------------------------------------------------------------

def test_no_public_default_secret_key_in_production(monkeypatch):
    class Prod(Config):
        SECRET_KEY = None
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    a, b = create_app(Prod), create_app(Prod)
    assert a.config["SECRET_KEY"] != b.config["SECRET_KEY"]
    assert "dev-only" not in a.config["SECRET_KEY"]


def test_secret_key_from_config_is_kept():
    class Prod(Config):
        SECRET_KEY = "from-env"
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    assert create_app(Prod).config["SECRET_KEY"] == "from-env"

