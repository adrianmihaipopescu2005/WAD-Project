from flask import Blueprint, render_template
from flask_login import current_user

from ...decorators import staff_required
from ...extensions import db
from ...models import ROLE_ASSISTANT, STATUS_ACTIVE, Absence, Student, User

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.get("/")
@staff_required
def index():
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
    return render_template("dashboard/index.html", stats=stats)
