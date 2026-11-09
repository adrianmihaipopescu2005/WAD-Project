from datetime import date

import pytest

from app import clock, create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import ROLE_ADMIN, ROLE_ASSISTANT, Student, Team, User

TODAY = date(2026, 10, 26)  # a Monday; the tests' fixed dates are relative to it
TUESDAY = date(2026, 10, 27)  # tomorrow: the earliest session a student may still report
THURSDAY = date(2026, 10, 29)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    """Pin "today" so the absence date window doesn't make the tests expire."""
    monkeypatch.setattr(clock, "today", lambda: TODAY)


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


def _make_user(email, role):
    user = User(email=email, name=email.split("@")[0], role=role)
    user.set_password("secret123")
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture
def make_user(app):
    return _make_user


@pytest.fixture
def admin(app):
    return _make_user("prof@example.com", ROLE_ADMIN)


@pytest.fixture
def assistant(app):
    return _make_user("assistant@example.com", ROLE_ASSISTANT)


def login(client, email, password="secret123", **query):
    return client.post("/login", query_string=query, data={"email": email, "password": password})


def add_team(assistant, *names, slot="TUE_18_20"):
    """A team of `names` (default: one student) owned by `assistant`."""
    team = Team(assistant=assistant, slot=slot,
                members=[Student(name=n) for n in (names or ("Ana Pop",))])
    _db.session.add(team)
    _db.session.commit()
    return team


def add_student(assistant, name="Ana Pop", slot="TUE_18_20"):
    """A student in a one-person team owned by `assistant`."""
    return add_team(assistant, name, slot=slot).members[0]
