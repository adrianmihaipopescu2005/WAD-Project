"""Demo data for `flask seed-demo`: an admin, two assistants, students and absences.

Dates are relative to `today`, so the demo always has upcoming Tuesday/Thursday sessions.
The passwords are public demo passwords, meant for local use only.
"""

from datetime import UTC, datetime, timedelta

from .extensions import db
from .models import (
    ROLE_ADMIN,
    ROLE_ASSISTANT,
    SOURCE_ASSISTANT,
    SOURCE_PUBLIC,
    STATUS_REVOKED,
    Absence,
    Student,
    User,
)

ADMIN = ("prof@demo.local", "Prof. Elena Ionescu", "demo-admin-123")
ASSISTANTS = [
    ("maria@demo.local", "Maria Popa", "demo-pass-123"),
    ("andrei@demo.local", "Andrei Dobre", "demo-pass-123"),
]
# (assistant index, student number, first name, last name, group)
STUDENTS = [
    (0, "LM1001", "Ana", "Popescu", "2.1"),
    (0, "LM1002", "Bogdan", "Marin", "2.1"),
    (0, "LM1003", "Cristina", "Stan", "2.2"),
    (0, "LM1004", "Dan", "Georgescu", "2.2"),
    (1, "LM2001", "Elena", "Radu", "3.1"),
    (1, "LM2002", "Florin", "Matei", "3.1"),
    (1, "LM2003", "Gabriela", "Tudor", "3.2"),
]
# (student number, slot, weeks from the next session, sessions, reason, source, revoked)
ABSENCES = [
    ("LM1001", "TUE_18_20", 0, 2, "Medical appointment, then recovery.", SOURCE_PUBLIC, False),
    ("LM1002", "THU_18_20", 0, 1, "Hackathon in Cluj.", SOURCE_PUBLIC, False),
    ("LM1003", "TUE_18_20", 1, 1, "Family event.", SOURCE_ASSISTANT, False),
    ("LM1004", "THU_18_20", 0, 1, "Overslept (reported late).", SOURCE_PUBLIC, True),
    ("LM2001", "THU_18_20", 0, 3, "Erasmus interview trip.", SOURCE_ASSISTANT, False),
    ("LM2002", "TUE_18_20", -1, 1, "Sick (last week).", SOURCE_PUBLIC, False),
]
WEEKDAY = {"TUE_18_20": 1, "THU_18_20": 3}


def _next_weekday(today, weekday):
    return today + timedelta(days=(weekday - today.weekday()) % 7)


def seed_demo(today=None):
    """Insert the demo data into an empty database, in one transaction."""
    today = today or datetime.now(UTC).date()

    def user(email, name, password, role):
        u = User(email=email, name=name, role=role)
        u.set_password(password)
        db.session.add(u)
        return u

    try:
        user(*ADMIN, ROLE_ADMIN)
        assistants = [user(*a, ROLE_ASSISTANT) for a in ASSISTANTS]
        students = {}
        for idx, number, first, last, group in STUDENTS:
            students[number] = Student(
                assistant=assistants[idx], student_number=number,
                first_name=first, last_name=last, study_group=group,
                email=f"{first}.{last}@student.demo.local".lower(),
            )
            db.session.add(students[number])
        for number, slot, weeks, sessions, reason, source, revoked in ABSENCES:
            start = _next_weekday(today, WEEKDAY[slot]) + timedelta(weeks=weeks)
            absence = Absence(
                student=students[number], slot=slot, start_date=start,
                sessions_count=sessions, reason=reason, source=source,
            )
            if revoked:
                absence.status = STATUS_REVOKED
                absence.revoked_at = datetime.now(UTC)
            db.session.add(absence)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
