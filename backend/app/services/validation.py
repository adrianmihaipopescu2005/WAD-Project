"""License validation (WAD): is a student excused from the lab session on a given date?"""

import hashlib
import secrets
from datetime import UTC, date, datetime

from ..extensions import db
from ..models import SLOTS, STATUS_ACTIVE, Absence, ApiKey
from .absences import find_student_by_number

KEY_PREFIX = "lam_"


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
    if user.api_key is not None:
        db.session.delete(user.api_key)
        db.session.flush()
    db.session.add(ApiKey(user=user, key_hash=_hash(raw)))
    db.session.commit()
    return raw


def revoke_key(user):
    if user.api_key is not None:
        db.session.delete(user.api_key)
        db.session.commit()


def user_for_key(raw_key):
    """The key's owner (and its last use is recorded), or None for a missing or unknown key."""
    if not raw_key:
        return None
    key = db.session.execute(
        db.select(ApiKey).where(ApiKey.key_hash == _hash(raw_key.strip()))
    ).scalar_one_or_none()
    if key is None:
        return None
    key.last_used_at = datetime.now(UTC)
    db.session.commit()
    return key.user


# --- validation -----------------------------------------------------------------------

def parse_day(value):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        raise ValidationError("date must be YYYY-MM-DD.") from None


def check_excused(user, student_number, day):
    """The validation result for `user`, who must be allowed to see the student.

    Another assistant's student gives the same 404 as an unknown number, so nothing leaks.
    """
    if not (student_number or "").strip():
        raise ValidationError("student_number is required.")
    student = find_student_by_number(student_number)
    if student is None or not (user.is_admin or student.assistant_id == user.id):
        raise ValidationError("Student not found.", 404)

    slot = next((code for code, (_label, wd) in SLOTS.items() if wd == day.weekday()), None)
    result = {
        "student_number": student.student_number,
        "date": day.isoformat(),
        "lab_day": slot is not None,
        "slot": slot,
        "slot_label": SLOTS[slot][0] if slot else None,
        "excused": False,
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
    covering = next((a for a in absences if a.covers(day)), None)
    if covering is not None:
        result.update(excused=True, absence_id=covering.id, until=covering.end_date.isoformat())
    return result
