from flask import Blueprint, render_template, request
from flask_login import current_user

from ...decorators import staff_required
from ...extensions import db
from ...models import (
    DECISION_PENDING,
    ROLE_ASSISTANT,
    STATUS_ACTIVE,
    Absence,
    Student,
    Team,
    User,
)
from ...services import validation
from ...services.teams import visible_students

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _stats():
    teams = db.select(db.func.count(Team.id))
    students = db.select(db.func.count(Student.id)).join(Student.team)
    active = (
        db.select(db.func.count(Absence.id))
        .join(Absence.student).join(Student.team)
        .where(Absence.status == STATUS_ACTIVE)
    )
    to_review = active.where(Absence.decision == DECISION_PENDING)
    if not current_user.is_admin:
        teams, students, active, to_review = (
            stmt.where(Team.assistant_id == current_user.id)
            for stmt in (teams, students, active, to_review)
        )

    stats = {
        "teams": db.session.scalar(teams),
        "students": db.session.scalar(students),
        "active_absences": db.session.scalar(active),
        "to_review": db.session.scalar(to_review),
    }
    if current_user.is_admin:
        stats["assistants"] = db.session.scalar(
            db.select(db.func.count(User.id)).where(User.role == ROLE_ASSISTANT)
        )
    return stats


def _excused_check():
    """Without JS the widget submits here, and the same check as the API is rendered."""
    student_id = request.args.get("student_id", "").strip()
    day = request.args.get("date", "").strip()
    if not (student_id or day):
        return None, None
    try:
        return validation.check_excused(
            current_user, validation.parse_student_id(student_id), validation.parse_day(day)
        ), None
    except validation.ValidationError as e:
        return None, str(e)


@bp.get("/")
@staff_required
def index():
    check, check_error = _excused_check()
    return render_template(
        "dashboard/index.html", stats=_stats(), check=check, check_error=check_error,
        students=visible_students(current_user),
    )
