from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ...decorators import staff_required
from ...models import SLOTS
from ...services import absences as service
from ...services.assistants import list_assistants
from ...services.auth import safe_next_url
from ...services.students import get_student, visible_students
from ...utils import wants_json
from .forms import AbsenceForm

bp = Blueprint("absences", __name__, url_prefix="/absences")


def _absence_or_404(absence_id):
    return service.get_absence(current_user, absence_id) or abort(404)


def _filters():
    args = request.args
    return {
        "student_id": args.get("student", type=int),
        "status": args.get("status") or None,
        "slot": args.get("slot") or None,
        "q": args.get("q", "").strip() or None,
        "assistant_id": args.get("assistant", type=int) if current_user.is_admin else None,
    }


def _results_context(filters):
    """Everything `absences/_results.html` needs. Shared by the page and its JSON search."""
    return {
        "absences": service.list_absences(current_user, **filters),
        "filtered": any(filters.values()),
        "next_url": url_for("absences.index", **request.args.to_dict()),
    }


@bp.get("/")
@staff_required
def index():
    filters = _filters()
    return render_template(
        "absences/list.html",
        filters=filters,
        students=visible_students(current_user),
        assistants=list_assistants() if current_user.is_admin else [],
        slots=SLOTS,
        **_results_context(filters),
    )


@bp.get("/search.json")
@staff_required
def search():
    """Live search: the same filters as the page, returning the rendered results."""
    ctx = _results_context(_filters())
    return {"count": len(ctx["absences"]), "html": render_template("absences/_results.html", **ctx)}


@bp.route("/new", methods=["GET", "POST"])
@staff_required
def new():
    students = visible_students(current_user)
    if not students:
        flash("Add a student before adding absences.", "warning")
        return redirect(url_for("students.new"))

    form = AbsenceForm()
    form.student_id.choices = [(s.id, f"{s.full_name} ({s.student_number})") for s in students]
    if request.method == "GET" and (preselect := request.args.get("student_id", type=int)):
        form.student_id.data = preselect

    if form.validate_on_submit():
        student = get_student(current_user, form.student_id.data) or abort(404)
        try:
            service.create_absence(
                student, form.slot.data, form.start_date.data,
                form.sessions_count.data, form.reason.data,
            )
        except service.AbsenceError as e:
            form.start_date.errors.append(str(e))
        else:
            flash(f"Absence added for {student.full_name}.", "success")
            return redirect(url_for("students.profile", student_id=student.id))
    return render_template("absences/form.html", form=form)


def _back():
    return redirect(safe_next_url(request.form.get("next")) or url_for("absences.index"))


def _action_done(absence, message):
    """Answer a revoke/extend: JSON with the re-rendered row for fetch(), else redirect back."""
    if not wants_json():
        flash(message, "success")
        return _back()
    row = render_template(
        "absences/_row.html",
        a=absence,
        show_student=request.form.get("show_student") == "1",
        next_url=safe_next_url(request.form.get("next")) or url_for("absences.index"),
    )
    return {
        "message": message,
        "absence": {
            "id": absence.id,
            "status": absence.status,
            "sessions_count": absence.sessions_count,
            "end_date": absence.end_date.isoformat(),
        },
        "html": row,
    }


def _action_failed(error):
    if wants_json():
        return {"error": str(error)}, error.status
    flash(str(error), "danger")
    return _back()


@bp.post("/<int:absence_id>/revoke")
@staff_required
def revoke(absence_id):
    absence = _absence_or_404(absence_id)
    try:
        service.revoke(absence)
    except service.AbsenceError as e:
        return _action_failed(e)
    return _action_done(absence, f"Absence of {absence.student.full_name} revoked.")


@bp.post("/<int:absence_id>/extend")
@staff_required
def extend(absence_id):
    absence = _absence_or_404(absence_id)
    try:
        service.extend(absence, request.form.get("sessions", type=int))
    except service.AbsenceError as e:
        return _action_failed(e)
    return _action_done(
        absence,
        f"Absence of {absence.student.full_name} extended to {absence.sessions_count} session(s),"
        f" until {absence.end_date.isoformat()}.",
    )
