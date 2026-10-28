from datetime import date

from app.models import STATUS_REVOKED, Absence, Student, Team, User
from app.seed import seed_demo


def _absence_of(db, name):
    return db.session.execute(
        db.select(Absence).join(Absence.student).where(Student.name == name)
    ).scalar_one()


def test_seed_demo_inserts_consistent_data(app, db):
    seed_demo(today=date(2026, 10, 26))  # a Monday
    assert db.session.scalar(db.select(db.func.count(User.id))) == 2  # admin + Darian
    assert db.session.scalar(db.select(db.func.count(Team.id))) == 5
    assert db.session.scalar(db.select(db.func.count(Student.id))) == 9
    absences = db.session.execute(db.select(Absence)).scalars().all()
    assert len(absences) == 6
    # All dates passed the DB slot/weekday CHECK. Relative dates are as expected:
    first = _absence_of(db, "Ana Popescu")
    assert first.start_date == date(2026, 10, 27) and first.motivated
    assert first.email == "ana.popescu@student.demo.local"
    assert any(a.status == STATUS_REVOKED for a in absences)
    assert {a.decision for a in absences} == {"pending", "motivated", "not_motivated"}


def test_seed_on_a_tuesday_uses_that_day(app, db):
    seed_demo(today=date(2026, 10, 27))
    assert _absence_of(db, "Ana Popescu").start_date == date(2026, 10, 27)


def test_seed_demo_cli(app, db):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    assert "prof@demo.local" in result.output and "darian@lab.local" in result.output

    result = runner.invoke(args=["seed-demo"])  # not empty any more
    assert result.exit_code != 0
    assert "--reset" in result.output

    result = runner.invoke(args=["seed-demo", "--reset"], input="n\n")  # aborted
    assert result.exit_code != 0
    assert db.session.scalar(db.select(db.func.count(User.id))) == 2

    result = runner.invoke(args=["seed-demo", "--reset"], input="y\n")
    assert result.exit_code == 0, result.output
    assert db.session.scalar(db.select(db.func.count(User.id))) == 2


def test_demo_logins_work(app, db, client):
    seed_demo(today=date(2026, 10, 26))
    res = client.post("/login", data={"email": "darian@lab.local", "password": "demo-pass-123"})
    assert res.status_code == 302


def test_import_teams_cli(app, db, tmp_path):
    seed_demo(today=date(2026, 10, 26))
    path = tmp_path / "teams.txt"
    path.write_text("Tuesday:\nPopescu Adrian Mihai    Urs Robert Sebastian\n", encoding="utf-8")
    runner = app.test_cli_runner()

    result = runner.invoke(args=["import-teams", str(path)])  # the only assistant: Darian
    assert result.exit_code == 0, result.output
    assert "Imported 1 team(s) for Darian" in result.output
    result = runner.invoke(args=["import-teams", str(path)])
    assert "skipped 1" in result.output

    result = runner.invoke(args=["import-teams", str(path), "--assistant", "nobody@x.com"])
    assert result.exit_code != 0 and "No lab assistant" in result.output

    path.write_text("Popescu Adrian Mihai | Someone Else\n", encoding="utf-8")
    result = runner.invoke(args=["import-teams", str(path)])
    assert result.exit_code != 0 and "Nothing was imported" in result.output


def test_reset_absences_keeps_users_and_teams(app, db):
    seed_demo(today=date(2026, 10, 26))
    runner = app.test_cli_runner()
    assert runner.invoke(args=["reset-absences"], input="n\n").exit_code != 0  # aborted
    assert db.session.scalar(db.select(db.func.count(Absence.id))) == 6

    result = runner.invoke(args=["reset-absences", "--yes"])
    assert result.exit_code == 0, result.output
    db.session.expire_all()
    assert db.session.scalar(db.select(db.func.count(Absence.id))) == 0
    assert db.session.scalar(db.select(db.func.count(Team.id))) == 5
    assert db.session.scalar(db.select(db.func.count(User.id))) == 2
