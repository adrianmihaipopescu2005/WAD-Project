from datetime import UTC, datetime

from sqlalchemy.orm import contains_eager

from ..extensions import db
from ..models import (
    MAX_SESSIONS,
    SLOTS,
    SOURCE_ASSISTANT,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    Absence,
    Student,
)
from .students import search_clause


class AbsenceError(Exception):
    """A rule violation shown to the user. `status` is the HTTP code for JSON responses."""

    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def slot_date_error(slot, day):
    """An error message if `day` isn't on `slot`'s weekday, else None."""
    if slot not in SLOTS:
        return "Choose a lab slot."
    label, weekday = SLOTS[slot]
    if day.weekday() != weekday:
        return f"{day.isoformat()} is not a {label.split()[0]}. Pick a date on the slot's day."
    return None


def _scoped(stmt, user):
    stmt = stmt.join(Absence.student).options(contains_eager(Absence.student))
    return stmt if user.is_admin else stmt.where(Student.assistant_id == user.id)


def list_absences(user, student_id=None, status=None, slot=None, q=None, assistant_id=None):
    """Absences visible to `user` (an assistant: only their students'), newest first."""
    stmt = _scoped(db.select(Absence), user)
    if user.is_admin and assistant_id:
        stmt = stmt.where(Student.assistant_id == assistant_id)
    if student_id:
        stmt = stmt.where(Absence.student_id == student_id)
    if status in (STATUS_ACTIVE, STATUS_REVOKED):
        stmt = stmt.where(Absence.status == status)
    if slot in SLOTS:
        stmt = stmt.where(Absence.slot == slot)
    if q:
        stmt = stmt.where(search_clause(q))
    stmt = stmt.order_by(Absence.start_date.desc(), Absence.id.desc())
    return db.session.execute(stmt).scalars().all()


def get_absence(user, absence_id):
    """The absence, or None if it doesn't exist or `user` may not see it."""
    stmt = _scoped(db.select(Absence).where(Absence.id == absence_id), user)
    return db.session.execute(stmt).scalar_one_or_none()


def create_absence(student, slot, start_date, sessions_count, reason, source=SOURCE_ASSISTANT):
    error = slot_date_error(slot, start_date)
    if error:
        raise AbsenceError(error, 400)
    if not 1 <= sessions_count <= MAX_SESSIONS:
        raise AbsenceError(f"Sessions must be between 1 and {MAX_SESSIONS}.", 400)
    reason = (reason or "").strip()
    if not reason:
        raise AbsenceError("A reason is required.", 400)

    absence = Absence(
        student=student, slot=slot, start_date=start_date,
        sessions_count=sessions_count, reason=reason, source=source,
    )
    db.session.add(absence)
    db.session.commit()
    return absence


def revoke(absence):
    """Mark the absence revoked. The row is kept."""
    if absence.status == STATUS_REVOKED:
        raise AbsenceError("This absence is already revoked.")
    absence.status = STATUS_REVOKED
    absence.revoked_at = datetime.now(UTC)
    db.session.commit()


def extend(absence, extra_sessions):
    """Cover `extra_sessions` more weekly sessions of the same slot."""
    if absence.status != STATUS_ACTIVE:
        raise AbsenceError("A revoked absence can't be extended.")
    if extra_sessions is None or extra_sessions < 1:
        raise AbsenceError("Add at least one session.", 400)
    if absence.sessions_count + extra_sessions > MAX_SESSIONS:
        raise AbsenceError(f"An absence can cover at most {MAX_SESSIONS} sessions.", 400)
    absence.sessions_count += extra_sessions
    db.session.commit()
