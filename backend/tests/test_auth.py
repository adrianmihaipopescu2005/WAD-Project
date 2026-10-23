import pytest
from conftest import login

from app import create_app
from app.config import TestingConfig
from app.decorators import admin_required
from app.extensions import db as _db
from app.models import Student
from app.services.auth import safe_next_url


def test_login_page_renders(client):
    res = client.get("/login")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'name="email"' in html
    assert 'name="password"' in html


def test_login_success_redirects_to_dashboard(client, admin):
    res = login(client, admin.email)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/dashboard/")
    html = client.get("/dashboard/").get_data(as_text=True)
    assert admin.name in html
    assert "Log out" in html


@pytest.mark.parametrize(
    ("email", "password"),
    [("prof@example.com", "wrong"), ("nobody@example.com", "secret123")],
)
def test_login_failure_same_message(client, admin, email, password):
    res = login(client, email, password)
    assert res.status_code == 200
    assert "Invalid email or password." in res.get_data(as_text=True)
    assert client.get("/dashboard/").status_code == 302


def test_login_email_is_case_insensitive(client, admin):
    assert login(client, "  PROF@Example.com ").status_code == 302


def test_login_missing_fields_shows_validation(client):
    res = client.post("/login", data={"email": "", "password": ""})
    assert res.status_code == 200
    assert "is-invalid" in res.get_data(as_text=True)


def test_login_follows_safe_next(client, admin):
    res = login(client, admin.email, next="/dashboard/?x=1")
    assert res.headers["Location"].endswith("/dashboard/?x=1")


@pytest.mark.parametrize("target", ["https://evil.com", "//evil.com", "evil.com", "/\\evil"])
def test_login_ignores_unsafe_next(client, admin, target):
    res = login(client, admin.email, next=target)
    assert res.headers["Location"].endswith("/dashboard/")


def test_safe_next_url():
    assert safe_next_url("/dashboard/") == "/dashboard/"
    assert safe_next_url(None) is None
    assert safe_next_url("https://evil.com/") is None
    assert safe_next_url("//evil.com") is None
    assert safe_next_url("/\\evil.com") is None


def test_logged_in_user_visiting_login_is_redirected(client, admin):
    login(client, admin.email)
    assert client.get("/login").headers["Location"].endswith("/dashboard/")


def test_logout_requires_post(client, admin):
    login(client, admin.email)
    assert client.get("/logout").status_code == 405
    res = client.post("/logout")
    assert res.status_code == 302
    assert client.get("/dashboard/").status_code == 302


def test_anonymous_redirected_to_login_with_next(client):
    res = client.get("/dashboard/")
    assert res.status_code == 302
    assert "/login?next=" in res.headers["Location"]


def test_navbar_for_anonymous(client):
    html = client.get("/").get_data(as_text=True)
    assert "Staff login" in html
    assert "Log out" not in html


def test_admin_required(app, admin, assistant):
    app.add_url_rule("/_admin-only", "admin_only", admin_required(lambda: "ok"))
    client = app.test_client()

    assert client.get("/_admin-only").status_code == 302  # anonymous → login

    login(client, assistant.email)
    assert client.get("/_admin-only").status_code == 403
    client.post("/logout")

    login(client, admin.email)
    assert client.get("/_admin-only").status_code == 200


def test_403_page_rendered(app, assistant):
    app.add_url_rule("/_admin-only", "admin_only", admin_required(lambda: "ok"))
    client = app.test_client()
    login(client, assistant.email)
    assert "Access denied" in client.get("/_admin-only").get_data(as_text=True)


def test_404_page_rendered(client):
    res = client.get("/does-not-exist")
    assert res.status_code == 404
    assert "Page not found" in res.get_data(as_text=True)


def test_dashboard_stats_scoped_per_assistant(client, db, admin, assistant, make_user):
    other = make_user("other@example.com", "assistant")
    db.session.add_all([
        Student(assistant=assistant, student_number="S1", first_name="A", last_name="A"),
        Student(assistant=other, student_number="S2", first_name="B", last_name="B"),
        Student(assistant=other, student_number="S3", first_name="C", last_name="C"),
    ])
    db.session.commit()

    login(client, assistant.email)
    html = client.get("/dashboard/").get_data(as_text=True)
    assert 'data-stat="students">1<' in html
    assert 'data-stat="assistants"' not in html
    client.post("/logout")

    login(client, admin.email)
    html = client.get("/dashboard/").get_data(as_text=True)
    assert 'data-stat="students">3<' in html
    assert 'data-stat="assistants">2<' in html


class CsrfConfig(TestingConfig):
    WTF_CSRF_ENABLED = True


@pytest.fixture
def csrf_client():
    app = create_app(CsrfConfig)
    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()


def test_login_post_without_csrf_token_rejected(csrf_client):
    res = csrf_client.post("/login", data={"email": "a@b.c", "password": "x"})
    assert res.status_code == 400


def test_login_form_contains_csrf_token(csrf_client):
    assert 'name="csrf_token"' in csrf_client.get("/login").get_data(as_text=True)
