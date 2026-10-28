"""Demo data for `flask seed-demo`: an admin, the lab assistant, teams and absences.

Dates are relative to `today`, so the demo always has upcoming Tuesday/Thursday sessions.
The passwords are public demo passwords, meant for local use only. The names are made up;
load the real teams with `flask import-teams`.
"""

from datetime import UTC, datetime, timedelta

from .extensions import db
from .models import (
    DECISION_MOTIVATED,
    DECISION_NOT_MOTIVATED,
    DECISION_PENDING,
    ROLE_ADMIN,
    ROLE_ASSISTANT,
    SLOTS,
    STATUS_REVOKED,
    Absence,
    Student,
    Team,
    User,
)

ADMIN = ("prof@demo.local", "Prof. Elena Ionescu", "demo-admin-123")
ASSISTANTS = [
    ("darian@lab.local", "Darian", "demo-pass-123"),
]
# (slot, member names)
TEAMS = [
    ("TUE_18_20", ["Ana Popescu", "Bogdan Marin"]),
    ("TUE_18_20", ["Cristina Stan", "Dan Georgescu"]),
    ("TUE_18_20", ["Ioana Vasile"]),
    ("THU_18_20", ["Elena Radu", "Florin Matei"]),
    ("THU_18_20", ["Gabriela Tudor", "Horia Lazar"]),
]
M, N, P = DECISION_MOTIVATED, DECISION_NOT_MOTIVATED, DECISION_PENDING
# (student name, weeks from the next session, sessions, reason, decision, revoked)
ABSENCES = [
    ("Ana Popescu", 0, 1, "Medical appointment (note attached by email).", M, False),
    ("Bogdan Marin", 0, 1, "Hackathon in Cluj.", P, False),
    ("Cristina Stan", 1, 1, "Family event.", P, False),
    ("Dan Georgescu", 0, 1, "Overslept.", N, True),
    ("Elena Radu", 0, 3, "Erasmus interview trip.", M, False),
    ("Gabriela Tudor", -1, 1, "Sick (last week).", M, False),
]


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
        assistant = [user(*a, ROLE_ASSISTANT) for a in ASSISTANTS][0]
        students = {}
        for slot, names in TEAMS:
            members = [Student(name=n) for n in names]
            db.session.add(Team(assistant=assistant, slot=slot, members=members))
            students.update((m.name, m) for m in members)
        for name, weeks, sessions, reason, decision, revoked in ABSENCES:
            student = students[name]
            slot = next(t[0] for t in TEAMS if name in t[1])
            start = _next_weekday(today, SLOTS[slot][1]) + timedelta(weeks=weeks)
            absence = Absence(
                student=student, slot=slot, start_date=start,
                sessions_count=sessions, reason=reason, decision=decision,
                email=f"{name.replace(' ', '.').lower()}@student.demo.local",
            )
            if revoked:
                absence.status = STATUS_REVOKED
                absence.revoked_at = datetime.now(UTC)
            db.session.add(absence)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
