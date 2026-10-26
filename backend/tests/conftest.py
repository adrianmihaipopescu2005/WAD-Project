from datetime import date

import pytest

from app import clock, create_app
from app.config import TestingConfig
from app.extensions import db as _db
from app.models import ROLE_ADMIN, ROLE_ASSISTANT, User

TODAY = date(2026, 10, 26)  # a Monday; the tests' fixed dates are relative to it


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
