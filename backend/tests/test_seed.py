from datetime import date

from app.models import SOURCE_PUBLIC, STATUS_REVOKED, Absence, Student, User
from app.seed import seed_demo


def test_seed_demo_inserts_consistent_data(app, db):
    seed_demo(today=date(2026, 10, 26))  # a Monday
    assert db.session.scalar(db.select(db.func.count(User.id))) == 3
    assert db.session.scalar(db.select(db.func.count(Student.id))) == 7
    absences = db.session.execute(db.select(Absence)).scalars().all()
    assert len(absences) == 6
    # All dates passed the DB slot/weekday CHECK. Relative dates are as expected:
    first = next(a for a in absences if a.student.student_number == "LM1001")
    assert first.start_date == date(2026, 10, 27) and first.sessions_count == 2
    assert any(a.status == STATUS_REVOKED for a in absences)
    assert any(a.source == SOURCE_PUBLIC for a in absences)


def test_seed_on_a_tuesday_uses_that_day(app, db):
    seed_demo(today=date(2026, 10, 27))
    first = db.session.execute(
        db.select(Absence).join(Absence.student).where(Student.student_number == "LM1001")
    ).scalar_one()
    assert first.start_date == date(2026, 10, 27)


def test_seed_demo_cli(app, db):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    assert "prof@demo.local" in result.output

    result = runner.invoke(args=["seed-demo"])  # not empty any more
    assert result.exit_code != 0
    assert "--reset" in result.output

    result = runner.invoke(args=["seed-demo", "--reset"], input="n\n")  # aborted
    assert result.exit_code != 0
    assert db.session.scalar(db.select(db.func.count(User.id))) == 3

    result = runner.invoke(args=["seed-demo", "--reset"], input="y\n")
    assert result.exit_code == 0, result.output
    assert db.session.scalar(db.select(db.func.count(User.id))) == 3


def test_demo_logins_work(app, db, client):
    seed_demo(today=date(2026, 10, 26))
    res = client.post("/login", data={"email": "maria@demo.local", "password": "demo-pass-123"})
    assert res.status_code == 302
