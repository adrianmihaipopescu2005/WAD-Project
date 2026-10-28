from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import ROLE_ASSISTANT, Team, User
from . import commit_or_rollback
from .auth import normalize_email

DUPLICATE_EMAIL = "A user with this email already exists."


class AssistantError(Exception):
    """A rule violation the admin should see as a message."""


def list_assistants():
    """All assistants, ordered by name, each paired with their team count."""
    count = (
        db.select(db.func.count(Team.id))
        .where(Team.assistant_id == User.id)
        .scalar_subquery()
    )
    rows = db.session.execute(
        db.select(User, count).where(User.role == ROLE_ASSISTANT).order_by(User.name)
    ).all()
    return [(user, teams) for user, teams in rows]


def get_assistant(assistant_id):
    user = db.session.get(User, assistant_id)
    return user if user is not None and user.role == ROLE_ASSISTANT else None


def email_taken(email):
    return db.session.execute(
        db.select(User.id).filter_by(email=normalize_email(email))
    ).first() is not None


def create_assistant(name, email, password):
    if email_taken(email):
        raise AssistantError(DUPLICATE_EMAIL)
    user = User(name=name.strip(), email=normalize_email(email), role=ROLE_ASSISTANT)
    user.set_password(password)
    db.session.add(user)
    try:
        commit_or_rollback()
    except IntegrityError:  # two admins adding the same email at once
        raise AssistantError(DUPLICATE_EMAIL) from None
    return user


def remove_assistant(assistant, reassign_to=None):
    """Delete `assistant`. Their teams (students, absences) first move to `reassign_to`, atomically.

    `reassign_to` is required when the assistant has teams.
    """
    has_teams = db.session.execute(
        db.select(Team.id).filter_by(assistant_id=assistant.id).limit(1)
    ).first() is not None

    if reassign_to is not None:
        if reassign_to.role != ROLE_ASSISTANT or reassign_to.id == assistant.id:
            raise AssistantError("Teams must be moved to a different lab assistant.")
    elif has_teams:
        raise AssistantError("Choose another assistant to take over this assistant's teams.")

    try:
        if has_teams:
            db.session.execute(
                db.update(Team)
                .where(Team.assistant_id == assistant.id)
                .values(assistant_id=reassign_to.id)
            )
        db.session.delete(assistant)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
