from datetime import UTC, datetime

from sqlalchemy.orm import contains_eager

from ..extensions import db
from ..models import (
    MAX_SESSIONS,
    SLOTS,
    SOURCE_ASSISTANT,
    SOURCE_PUBLIC,
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


# --- public (no login) ---------------------------------------------------------------

def find_student_by_number(student_number):
    number = (student_number or "").strip()
    if not number:
        return None
    return db.session.execute(
        db.select(Student).where(Student.student_number == number)
    ).scalar_one_or_none()


def public_lookup(student_number):
    """What the public form may reveal about a student number: initials and group only."""
    student = find_student_by_number(student_number)
    if student is None:
        return {"found": False}
    initials = f"{student.first_name[:1].upper()}. {student.last_name[:1].upper()}."
    return {"found": True, "initials": initials, "group": student.study_group}


def _covering_absence(student, slot, day):
    stmt = db.select(Absence).where(
        Absence.student_id == student.id, Absence.slot == slot, Absence.status == STATUS_ACTIVE
    )
    return next((a for a in db.session.execute(stmt).scalars() if a.covers(day)), None)


def submit_public(student_number, slot, start_date, sessions_count, reason):
    """A student's own report. It goes to the assistant who registered their student number."""
    student = find_student_by_number(student_number)
    if student is None:
        raise AbsenceError("Student number not found. Contact your lab assistant.", 404)
    if slot in SLOTS and _covering_absence(student, slot, start_date):
        raise AbsenceError("You already reported an absence for this session.")
    return create_absence(student, slot, start_date, sessions_count, reason, SOURCE_PUBLIC)
