from flask import Blueprint, render_template, request
from flask_login import current_user

from ...decorators import staff_required
from ...extensions import db
from ...models import ROLE_ASSISTANT, STATUS_ACTIVE, Absence, Student, User
from ...services import validation

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _stats():
    students = db.select(db.func.count(Student.id))
    absences = (
        db.select(db.func.count(Absence.id))
        .join(Absence.student)
        .where(Absence.status == STATUS_ACTIVE)
    )
    if not current_user.is_admin:
        students = students.where(Student.assistant_id == current_user.id)
        absences = absences.where(Student.assistant_id == current_user.id)

    stats = {
        "students": db.session.scalar(students),
        "active_absences": db.session.scalar(absences),
    }
    if current_user.is_admin:
        stats["assistants"] = db.session.scalar(
            db.select(db.func.count(User.id)).where(User.role == ROLE_ASSISTANT)
        )
    return stats


def _excused_check():
    """Without JS the widget submits here, and the same check as the API is rendered."""
    number = request.args.get("student_number", "").strip()
    day = request.args.get("date", "").strip()
    if not (number or day):
        return None, None
    try:
        return validation.check_excused(current_user, number, validation.parse_day(day)), None
    except validation.ValidationError as e:
        return None, str(e)


@bp.get("/")
@staff_required
def index():
    check, check_error = _excused_check()
    return render_template(
        "dashboard/index.html", stats=_stats(), check=check, check_error=check_error,
    )
