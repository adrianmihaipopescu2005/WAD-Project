from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import contains_eager

from .. import clock
from ..extensions import db
from ..models import (
    DAYS_AHEAD,
    DECISION_MOTIVATED,
    DECISION_NOT_MOTIVATED,
    DECISIONS,
    MAX_SESSIONS,
    SLOTS,
    STATUS_ACTIVE,
    STATUS_REVOKED,
    Absence,
    Student,
    Team,
)
from . import commit_or_rollback, mail
from .teams import search_clause

# Deliberately vague: it must not reveal whether a student is already absent on a date.
DUPLICATE_PUBLIC_MESSAGE = (
    "This report couldn't be recorded. If you already reported this session, there's nothing "
    "more to do. Otherwise, contact your lab assistant."
)


class AbsenceError(Exception):
    """A rule violation shown to the user. `status` is the HTTP code for JSON responses."""

    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def date_window():
    """The (earliest, latest) date a student may report: from tomorrow to about 6 months ahead.

    "Tomorrow" means a session can be reported until 23:59 the day before (Romanian time).
    """
    today = clock.today()
    return today + timedelta(days=1), today + timedelta(days=DAYS_AHEAD)


def slot_date_error(slot, day):
    """An error message if `day` isn't on `slot`'s weekday or is outside the window, else None."""
    if slot not in SLOTS:
        return "Choose a lab slot."
    label, weekday = SLOTS[slot]
    day_name = label.split()[0]
    if day.weekday() != weekday:
        return f"{day.isoformat()} is not a {day_name}. Your team's lab is on {day_name}s."
    earliest, latest = date_window()
    if day < earliest:
        return (
            f"Too late to report the {day.isoformat()} session. Absences must be reported by "
            f"23:59 the day before ({(day - timedelta(days=1)).strftime('%A')} for {day_name})."
        )
    if day > latest:
        return f"Pick a date until {latest.isoformat()} (about 6 months ahead)."
    return None


def _scoped(stmt, user):
    stmt = (
        stmt.join(Absence.student).join(Student.team)
        .options(contains_eager(Absence.student).contains_eager(Student.team))
    )
    return stmt if user.is_admin else stmt.where(Team.assistant_id == user.id)


def list_absences(
    user, student_id=None, status=None, slot=None, q=None, assistant_id=None, decision=None
):
    """Absences visible to `user` (an assistant: only their teams'), newest first."""
    stmt = _scoped(db.select(Absence), user)
    if user.is_admin and assistant_id:
        stmt = stmt.where(Team.assistant_id == assistant_id)
    if student_id:
        stmt = stmt.where(Absence.student_id == student_id)
    if status in (STATUS_ACTIVE, STATUS_REVOKED):
        stmt = stmt.where(Absence.status == status)
    if slot in SLOTS:
        stmt = stmt.where(Absence.slot == slot)
    if decision in DECISIONS:
        stmt = stmt.where(Absence.decision == decision)
    if q:
        stmt = stmt.where(search_clause(q))
    stmt = stmt.order_by(Absence.start_date.desc(), Absence.id.desc())
    return db.session.execute(stmt).scalars().all()


def get_absence(user, absence_id):
    """The absence, or None if it doesn't exist or `user` may not see it."""
    stmt = _scoped(db.select(Absence).where(Absence.id == absence_id), user)
    return db.session.execute(stmt).scalar_one_or_none()


def revoke(absence):
    """Mark the absence revoked. The row is kept."""
    if absence.status == STATUS_REVOKED:
        raise AbsenceError("This absence is already revoked.")
    absence.status = STATUS_REVOKED
    absence.revoked_at = datetime.now(UTC)
    commit_or_rollback()


def extend(absence, extra_sessions):
    """Cover `extra_sessions` more weekly sessions of the same slot."""
    if absence.status != STATUS_ACTIVE:
        raise AbsenceError("A revoked absence can't be extended.")
    if extra_sessions is None or extra_sessions < 1:
        raise AbsenceError("Add at least one session.", 400)
    if absence.sessions_count + extra_sessions > MAX_SESSIONS:
        raise AbsenceError(f"An absence can cover at most {MAX_SESSIONS} sessions.", 400)
    absence.sessions_count += extra_sessions
    commit_or_rollback()


def decide(absence, decision, staff):
    """Mark the absence motivated or not motivated, then email the student.

    The decision is saved first; returns whether the email was sent. Choosing the current
    decision again just re-sends the email (e.g. after a failed send).
    """
    if decision not in (DECISION_MOTIVATED, DECISION_NOT_MOTIVATED):
        raise AbsenceError("Choose motivated or not motivated.", 400)
    if absence.status != STATUS_ACTIVE:
        raise AbsenceError("A revoked absence can't be decided.")
    absence.decision = decision
    absence.decided_at = datetime.now(UTC)
    absence.notified_at = None
    commit_or_rollback()

    sent = mail.send(absence.email, *decision_email(absence, staff))
    if sent:
        absence.notified_at = datetime.now(UTC)
        commit_or_rollback()
    return sent


def decision_email(absence, staff):
    """(subject, body) of the email telling the student the decision."""
    word = "motivated" if absence.motivated else "not motivated"
    date = absence.start_date.strftime("%A %d %B %Y")
    subject = f"Your lab absence on {absence.start_date.isoformat()} was {word}"
    covers = (
        f"It covers {absence.sessions_count} weekly sessions, until "
        f"{absence.end_date.isoformat()}.\n" if absence.sessions_count > 1 else ""
    )
    outcome = (
        "You are excused from this lab session." if absence.motivated else
        "This absence is not excused. If you think this is a mistake, talk to your lab assistant."
    )
    body = (
        f"Hi {absence.student.name},\n\n"
        f"Your absence from the Mobile Systems and Applications lab ({absence.slot_label}) on "
        f"{date} was marked {word.upper()} by {staff.name}.\n"
        f"{covers}\n"
        f"{outcome}\n\n"
        f"The reason you gave: {absence.reason}\n\n"
        "This is an automatic message from the Lab Absence Manager.\n"
    )
    return subject, body


# --- public (no login) ---------------------------------------------------------------

def public_teams():
    """Every team with its members, for the public form: by slot, then in the order added."""
    stmt = db.select(Team).order_by(Team.slot.desc(), Team.id)  # TUE_ before THU_
    return [t for t in db.session.execute(stmt).scalars() if t.members]


def _overlaps_active(student, slot, start_date, sessions_count):
    """True if any session in the new range is already covered by an active absence."""
    days = [start_date + timedelta(weeks=i) for i in range(sessions_count)]
    stmt = db.select(Absence).where(
        Absence.student_id == student.id, Absence.slot == slot, Absence.status == STATUS_ACTIVE
    )
    return any(a.covers(day) for a in db.session.execute(stmt).scalars() for day in days)


def submit_public(student_id, start_date, reason, email):
    """A student's own report of one session. The slot is their team's slot."""
    student = db.session.get(Student, student_id) if student_id else None
    if student is None:
        raise AbsenceError("Choose your team and your name.", 404)
    slot = student.team.slot
    error = slot_date_error(slot, start_date)
    if error:
        raise AbsenceError(error, 400)
    reason = (reason or "").strip()
    if not reason:
        raise AbsenceError("A reason is required.", 400)
    email = (email or "").strip().lower()
    if not email:
        raise AbsenceError("An email address is required.", 400)
    if _overlaps_active(student, slot, start_date, 1):
        raise AbsenceError(DUPLICATE_PUBLIC_MESSAGE)

    absence = Absence(
        student=student, slot=slot, start_date=start_date, reason=reason, email=email
    )
    db.session.add(absence)
    commit_or_rollback()
    return absence
