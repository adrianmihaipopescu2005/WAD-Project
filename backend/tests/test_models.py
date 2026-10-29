from datetime import date

import pytest
from conftest import THURSDAY, TUESDAY, add_student, add_team
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import STATUS_REVOKED, Absence, Student, Team, User

MONDAY = date(2026, 10, 26)


def _add_and_expect_integrity_error(db, obj):
    db.session.add(obj)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_foreign_keys_enabled(db):
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_password_is_hashed(assistant):
    assert assistant.password_hash != "secret123"
    assert assistant.check_password("secret123")
    assert not assistant.check_password("wrong")


def test_invalid_role_rejected(db):
    _add_and_expect_integrity_error(
        db, User(email="x@example.com", name="x", password_hash="h", role="professor")
    )


def test_team_requires_existing_assistant(db):
    _add_and_expect_integrity_error(db, Team(assistant_id=999, slot="TUE_18_20"))


def test_team_slot_checked(db, assistant):
    _add_and_expect_integrity_error(db, Team(assistant=assistant, slot="FRI_18_20"))


def test_student_requires_existing_team(db):
    _add_and_expect_integrity_error(db, Student(team_id=999, name="Ghost"))


def test_cannot_delete_assistant_with_teams(db, assistant):
    add_team(assistant)
    # RESTRICT fails on the DELETE statement itself, not on commit.
    with pytest.raises(IntegrityError):
        db.session.execute(text("DELETE FROM users WHERE id = :id"), {"id": assistant.id})
    db.session.rollback()


def test_team_label_and_teammates(assistant):
    team = add_team(assistant, "Ana Pop", "Ion Ionescu")
    assert team.label == "Ana Pop & Ion Ionescu"
    ana, ion = team.members
    assert ana.teammates == [ion] and ion.teammates == [ana]
    assert ana.initials == "AP"


def test_valid_absences_accepted(db, assistant):
    s = add_student(assistant)
    db.session.add_all([
        Absence(
            email="s@example.com",
            student=s, slot="TUE_18_20", start_date=TUESDAY, reason="Doctor"),
        Absence(
            email="s@example.com",
            student=s, slot="THU_18_20", start_date=THURSDAY, reason="Exam", sessions_count=2),
    ])
    db.session.commit()
    assert len(s.absences) == 2
    assert s.absences[0].decision == "pending"  # staff decide later


@pytest.mark.parametrize(
    ("slot", "day"),
    [("TUE_18_20", MONDAY), ("TUE_18_20", THURSDAY), ("THU_18_20", TUESDAY), ("FRI_18_20", MONDAY)],
)
def test_slot_weekday_mismatch_rejected(db, assistant, slot, day):
    s = add_student(assistant)
    _add_and_expect_integrity_error(db, Absence(
        email="s@example.com", student=s, slot=slot, start_date=day, reason="x"))


def test_sessions_count_must_be_positive(db, assistant):
    s = add_student(assistant)
    _add_and_expect_integrity_error(
        db, Absence(
            email="s@example.com",
            student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x", sessions_count=0)
    )


def test_invalid_status_rejected(db, assistant):
    s = add_student(assistant)
    _add_and_expect_integrity_error(
        db, Absence(
            email="s@example.com",
            student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x", status="pending")
    )


def test_deleting_team_deletes_students_and_absences(db, assistant):
    s = add_student(assistant)
    db.session.add(Absence(
        email="s@example.com", student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x"))
    db.session.commit()
    # Through the DB's ON DELETE CASCADE, not only the ORM.
    db.session.execute(text("DELETE FROM teams"))
    db.session.commit()
    assert db.session.execute(db.select(Student)).first() is None
    assert db.session.execute(db.select(Absence)).first() is None


def test_covers():
    a = Absence(slot="TUE_18_20", start_date=TUESDAY, sessions_count=2, status="active")
    assert a.covers(TUESDAY)
    assert a.covers(date(2026, 11, 3))  # next Tuesday
    assert not a.covers(date(2026, 11, 10))  # third week, not covered
    assert not a.covers(date(2026, 10, 20))  # before start
    assert not a.covers(THURSDAY)  # other weekday
    a.status = STATUS_REVOKED
    assert not a.covers(TUESDAY)


@pytest.mark.parametrize(("decision", "excused"),
                         [("pending", False), ("not_motivated", False), ("motivated", True)])
def test_excuses_needs_motivated(decision, excused):
    a = Absence(slot="TUE_18_20", start_date=TUESDAY, sessions_count=1, status="active",
                decision=decision)
    assert a.covers(TUESDAY)
    assert a.excuses(TUESDAY) is excused


def test_decision_checked_and_email_required(db, assistant):
    s = add_student(assistant)
    _add_and_expect_integrity_error(db, Absence(
        email="s@example.com", student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x",
        decision="maybe",
    ))
    _add_and_expect_integrity_error(
        db, Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x")
    )
