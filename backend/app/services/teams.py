import re

from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import SLOTS, STATUS_ACTIVE, TEAM_SIZE, Absence, Student, Team
from . import commit_or_rollback


class TeamError(Exception):
    """A rule violation the user should see as a form error."""


def _escape_like(q):
    """Escape LIKE wildcards so "%" and "_" in the search box match literally."""
    return q.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def search_clause(q):
    """WHERE clause matching a student's name (case-insensitive). Needs Student in the query."""
    return Student.name.ilike(f"%{_escape_like(q)}%", escape="\\")


def normalize_name(name):
    """Trim and collapse inner whitespace: "  Ion   Popescu " → "Ion Popescu"."""
    return " ".join((name or "").split())


def visible_students(user):
    """All students `user` may see, ordered by name (for select boxes)."""
    stmt = db.select(Student).join(Student.team).order_by(Student.name)
    if not user.is_admin:
        stmt = stmt.where(Team.assistant_id == user.id)
    return db.session.execute(stmt).scalars().all()


def list_teams(user, assistant_id=None, q=None, slot=None):
    """Teams visible to `user`, each with the count of their members' active absences."""
    active = (
        db.select(db.func.count(Absence.id))
        .join(Absence.student)
        .where(Student.team_id == Team.id, Absence.status == STATUS_ACTIVE)
        .scalar_subquery()
    )
    stmt = db.select(Team, active).options(selectinload(Team.members))
    if not user.is_admin:
        stmt = stmt.where(Team.assistant_id == user.id)
    elif assistant_id:
        stmt = stmt.where(Team.assistant_id == assistant_id)
    if slot in SLOTS:
        stmt = stmt.where(Team.slot == slot)
    if q:
        stmt = stmt.where(Team.members.any(search_clause(q)))
    stmt = stmt.order_by(Team.slot.desc(), Team.id)  # Tuesday teams first, then in the order added
    return db.session.execute(stmt).all()


def get_team(user, team_id):
    """The team, or None if it doesn't exist or `user` may not see it."""
    stmt = db.select(Team).where(Team.id == team_id)
    if not user.is_admin:
        stmt = stmt.where(Team.assistant_id == user.id)
    return db.session.execute(stmt).scalar_one_or_none()


def get_student(user, student_id):
    """The student, or None if it doesn't exist or `user` may not see it."""
    stmt = db.select(Student).join(Student.team).where(Student.id == student_id)
    if not user.is_admin:
        stmt = stmt.where(Team.assistant_id == user.id)
    return db.session.execute(stmt).scalar_one_or_none()


def _check_names(names, team=None):
    """The cleaned member names. Each must be unique: one student is in exactly one team."""
    names = [n for n in (normalize_name(n) for n in names) if n]
    if not 1 <= len(names) <= TEAM_SIZE:
        raise TeamError(f"A team has 1 to {TEAM_SIZE} students.")
    if len({n.lower() for n in names}) != len(names):
        raise TeamError("The two students must have different names.")
    for name in names:
        stmt = db.select(Student).where(db.func.lower(Student.name) == name.lower())
        if team is not None and team.id is not None:
            stmt = stmt.where(Student.team_id != team.id)
        other = db.session.execute(stmt.limit(1)).scalar_one_or_none()
        if other is not None:
            raise TeamError(f"{other.name} is already in another team ({other.team.slot_label}).")
    return names


def create_team(assistant_id, slot, names):
    if slot not in SLOTS:
        raise TeamError("Choose a lab slot.")
    names = _check_names(names)
    team = Team(assistant_id=assistant_id, slot=slot, members=[Student(name=n) for n in names])
    db.session.add(team)
    commit_or_rollback()
    return team


def update_team(team, slot, names, assistant_id=None):
    """Rename members in place (their absences stay). A removed member is deleted with their
    absences. `assistant_id` reassigns the team (admins only; the route enforces that)."""
    if slot not in SLOTS:
        raise TeamError("Choose a lab slot.")
    names = _check_names(names, team)
    members = list(team.members)
    for i, name in enumerate(names):
        if i < len(members):
            members[i].name = name
        else:
            team.members.append(Student(name=name))
    for extra in members[len(names):]:
        db.session.delete(extra)
    team.slot = slot
    if assistant_id is not None:
        team.assistant_id = assistant_id
    commit_or_rollback()
    return team


def delete_team(team):
    """Delete the team. Its students and their absences go with it (FK ON DELETE CASCADE)."""
    db.session.delete(team)
    commit_or_rollback()


# --- import (flask import-teams) --------------------------------------------------------

DAY_HEADERS = {
    label.split()[0].lower(): code for code, (label, _weekday) in SLOTS.items()
}
# Two names on a line, separated by "|", a tab, or two or more spaces.
NAME_SEPARATOR = re.compile(r"\s*\|\s*|\t+|\s{2,}")


def parse_teams(text):
    """[(slot, [name, name]), …] from lines like "Tuesday:" followed by "Name One | Name Two"."""
    teams, slot = [], None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        header = line.rstrip(":").strip().lower()
        if header in DAY_HEADERS:
            slot = DAY_HEADERS[header]
            continue
        if slot is None:
            raise TeamError(
                f"Line {lineno}: put a 'Tuesday:' or 'Thursday:' line before the teams."
            )
        names = [normalize_name(n.lstrip("-–")) for n in NAME_SEPARATOR.split(line)]
        teams.append((slot, [n for n in names if n]))
    return teams


def import_teams(assistant, text):
    """Create the parsed teams for `assistant` in one transaction.

    A team whose members all exist already (in any order) is skipped, so importing twice is safe.
    Returns (created, skipped).
    """
    created = skipped = 0
    try:
        for slot, names in parse_teams(text):
            existing = {
                n.lower() for n in db.session.execute(
                    db.select(Student.name).where(
                        db.func.lower(Student.name).in_([n.lower() for n in names])
                    )
                ).scalars()
            }
            if existing and existing == {n.lower() for n in names}:
                skipped += 1
                continue
            team = Team(assistant=assistant, slot=slot,
                        members=[Student(name=n) for n in _check_names(names)])
            db.session.add(team)
            db.session.flush()  # later lines see this team in the duplicate checks
            created += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return created, skipped
