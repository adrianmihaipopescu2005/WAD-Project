"""Student accounts (decided 2026-10-29): a student sees the status of their own absences.

An account is only created from a link emailed to the address, and the password is chosen on
the page that link opens. So whoever has the account also has the inbox, and sees exactly the
absences reported with that email. The same link resets a forgotten password.
"""

import hashlib

from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import db
from ..models import DECISIONS, ROLE_STUDENT, STATUS_ACTIVE, Absence, User
from . import commit_or_rollback, mail
from .auth import normalize_email

LINK_MAX_AGE_SECONDS = 24 * 60 * 60
_SALT = "student-password-link"


class AccountError(Exception):
    """A link that is invalid, expired, already used, or for a staff email."""


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def _fingerprint(user):
    """Changes when the password changes, so each link works only once."""
    if user is None:
        return ""
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def _user_by_email(email):
    return db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()


def request_link(name, email):
    """Email a set-password link. Returns nothing, so the page can't reveal who has an account.

    Staff emails get nothing: staff passwords are managed by the admin.
    """
    email = normalize_email(email)
    user = _user_by_email(email)
    if user is not None and not user.is_student:
        return
    token = _serializer().dumps(
        {"email": email, "name": name, "fp": _fingerprint(user)}
    )
    link = url_for("student.set_password", token=token, _external=True)
    if user is None:
        subject = "Create your Lab Absence Manager account"
        intro = "Open this link to choose a password and create your account:"
    else:
        subject = "Reset your Lab Absence Manager password"
        intro = "Open this link to choose a new password for your account:"
    body = (
        f"Hi {user.name if user else name},\n\n"
        f"{intro}\n{link}\n\n"
        "The link works once, for 24 hours. If you didn't ask for it, ignore this email.\n\n"
        "With the account you can see the status of every absence you reported with this "
        "email address.\n"
    )
    if not mail.send(email, subject, body) and current_app.debug:
        # Local runs often have no MAIL_* settings: show the link so sign-up can be tried.
        current_app.logger.warning("Email not sent. Set-password link for %s: %s", email, link)


def read_link(token):
    """The link's {"email", "name", "user"}, or AccountError if it can't be used."""
    try:
        data = _serializer().loads(token, max_age=LINK_MAX_AGE_SECONDS)
    except SignatureExpired:
        raise AccountError("This link has expired. Ask for a new one.") from None
    except BadSignature:
        raise AccountError("This link is not valid. Ask for a new one.") from None
    user = _user_by_email(data["email"])
    if user is not None and not user.is_student:
        raise AccountError("This link is not valid. Ask for a new one.")
    if data["fp"] != _fingerprint(user):
        raise AccountError("This link was already used. Ask for a new one.")
    return {"email": data["email"], "name": data["name"], "user": user}


def set_password(token, password):
    """Create the student account (or set a new password) from a link. Returns the user."""
    link = read_link(token)
    user = link["user"]
    if user is None:
        user = User(email=link["email"], name=link["name"], role=ROLE_STUDENT)
        db.session.add(user)
    user.set_password(password)
    commit_or_rollback()
    return user


def own_absences(user, decision=None):
    """The absences reported with this student's email, newest session first."""
    stmt = db.select(Absence).where(Absence.email == user.email)
    if decision in DECISIONS:
        stmt = stmt.where(Absence.decision == decision, Absence.status == STATUS_ACTIVE)
    stmt = stmt.order_by(Absence.start_date.desc(), Absence.id.desc())
    return db.session.execute(stmt).scalars().all()


def decision_counts(user):
    """{decision: count} of this student's active absences, every decision included."""
    rows = db.session.execute(
        db.select(Absence.decision, db.func.count(Absence.id))
        .where(Absence.email == user.email, Absence.status == STATUS_ACTIVE)
        .group_by(Absence.decision)
    ).all()
    return {d: 0 for d in DECISIONS} | dict(rows)
