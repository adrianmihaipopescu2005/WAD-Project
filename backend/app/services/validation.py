"""License validation (WAD): is a student excused from the lab session on a given date?"""

import hashlib
import re
import secrets
from datetime import UTC, date, datetime, timedelta

from ..extensions import db
from ..models import SLOTS, STATUS_ACTIVE, Absence, ApiKey
from . import commit_or_rollback
from .teams import get_student

KEY_PREFIX = "lam_"
LAST_USED_RESOLUTION = timedelta(minutes=1)
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class ValidationError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# --- API keys -------------------------------------------------------------------------

def _hash(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key(user):
    """Create (or replace) the user's key and return the raw key, which is never stored."""
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    try:
        if user.api_key is not None:
            db.session.delete(user.api_key)
            db.session.flush()  # free the unique user_id before inserting the new key
        db.session.add(ApiKey(user=user, key_hash=_hash(raw)))
        db.session.commit()
    except Exception:
        db.session.rollback()  # the old key stays valid
        raise
    return raw


def revoke_key(user):
    if user.api_key is not None:
        db.session.delete(user.api_key)
        commit_or_rollback()


def user_for_key(raw_key):
    """The key's owner, or None for a missing or unknown key. Records the last use."""
    if not raw_key:
        return None
    key = db.session.execute(
        db.select(ApiKey).where(ApiKey.key_hash == _hash(raw_key.strip()))
    ).scalar_one_or_none()
    if key is None:
        return None
    _touch(key)
    return key.user


def _touch(key):
    """Update last_used_at at most once a minute, so every API call isn't a SQLite write."""
    now = datetime.now(UTC)
    last = key.last_used_at
    if last is not None and last.tzinfo is None:  # SQLite returns naive datetimes
        last = last.replace(tzinfo=UTC)
    if last is not None and now - last < LAST_USED_RESOLUTION:
        return
    key.last_used_at = now
    try:
        commit_or_rollback()
    except Exception:  # a lost timestamp is harmless; never fail the API call for it
        pass


# --- validation -----------------------------------------------------------------------

def parse_day(value):
    value = (value or "").strip()
    # date.fromisoformat also accepts forms like "20261027" and "2026-W44-2". Only allow YYYY-MM-DD.
    if not DATE_PATTERN.fullmatch(value):
        raise ValidationError("date must be YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError("date must be YYYY-MM-DD.") from None


def parse_student_id(value):
    value = (value or "").strip()
    if not value:
        raise ValidationError("student_id is required.")
    if not value.isdigit():
        raise ValidationError("student_id must be a number.")
    return int(value)


def check_excused(user, student_id, day):
    """The validation result for `user`, who must be allowed to see the student.

    Another assistant's student gives the same 404 as an unknown id, so nothing leaks.
    A student is excused only by an active absence that staff marked motivated.
    """
    student = get_student(user, student_id)
    if student is None:
        raise ValidationError("Student not found.", 404)

    slot = next((code for code, (_label, wd) in SLOTS.items() if wd == day.weekday()), None)
    result = {
        "student_id": student.id,
        "student_name": student.name,
        "date": day.isoformat(),
        "lab_day": slot is not None,
        "slot": slot,
        "slot_label": SLOTS[slot][0] if slot else None,
        "excused": False,
        "reported": False,
        "motivated": False,
        "decision": None,
        "absence_id": None,
        "until": None,
    }
    if slot is None:
        return result

    absences = db.session.execute(
        db.select(Absence).where(
            Absence.student_id == student.id,
            Absence.slot == slot,
            Absence.status == STATUS_ACTIVE,
        )
    ).scalars()
    covering = sorted((a for a in absences if a.covers(day)), key=lambda a: not a.motivated)
    if covering:
        a = covering[0]  # a motivated one wins over a pending or not motivated one
        result.update(
            excused=a.motivated, reported=True, motivated=a.motivated, decision=a.decision,
            absence_id=a.id, until=a.end_date.isoformat(),
        )
    return result
