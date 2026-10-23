from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import STATUS_REVOKED, Absence, Student, User

TUESDAY = date(2026, 10, 27)
THURSDAY = date(2026, 10, 29)
MONDAY = date(2026, 10, 26)


def _student(db, assistant, number="S001"):
    s = Student(assistant=assistant, student_number=number, first_name="Ana", last_name="Pop")
    db.session.add(s)
    db.session.commit()
    return s


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
        db, User(email="x@example.com", name="x", password_hash="h", role="student")
    )


def test_student_number_unique(db, assistant):
    _student(db, assistant, "S001")
    _add_and_expect_integrity_error(
        db, Student(assistant=assistant, student_number="S001", first_name="B", last_name="C")
    )


def test_student_requires_existing_assistant(db):
    _add_and_expect_integrity_error(
        db, Student(assistant_id=999, student_number="S9", first_name="B", last_name="C")
    )


def test_cannot_delete_assistant_with_students(db, assistant):
    _student(db, assistant)
    # RESTRICT fails on the DELETE statement itself, not on commit.
    with pytest.raises(IntegrityError):
        db.session.execute(text("DELETE FROM users WHERE id = :id"), {"id": assistant.id})
    db.session.rollback()


def test_valid_absences_accepted(db, assistant):
    s = _student(db, assistant)
    db.session.add_all([
        Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="Doctor"),
        Absence(student=s, slot="THU_18_20", start_date=THURSDAY, reason="Exam", sessions_count=2),
    ])
    db.session.commit()
    assert len(s.absences) == 2


@pytest.mark.parametrize(
    ("slot", "day"),
    [("TUE_18_20", MONDAY), ("TUE_18_20", THURSDAY), ("THU_18_20", TUESDAY), ("FRI_18_20", MONDAY)],
)
def test_slot_weekday_mismatch_rejected(db, assistant, slot, day):
    s = _student(db, assistant)
    _add_and_expect_integrity_error(db, Absence(student=s, slot=slot, start_date=day, reason="x"))


def test_sessions_count_must_be_positive(db, assistant):
    s = _student(db, assistant)
    _add_and_expect_integrity_error(
        db, Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x", sessions_count=0)
    )


def test_invalid_status_rejected(db, assistant):
    s = _student(db, assistant)
    _add_and_expect_integrity_error(
        db, Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x", status="pending")
    )


def test_deleting_student_deletes_absences(db, assistant):
    s = _student(db, assistant)
    db.session.add(Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x"))
    db.session.commit()
    db.session.delete(s)
    db.session.commit()
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
