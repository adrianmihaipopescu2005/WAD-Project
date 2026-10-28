from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ...decorators import staff_required
from ...models import SLOTS
from ...services import absences as service
from ...services.assistants import list_assistants
from ...services.auth import safe_next_url
from ...services.teams import visible_students
from ...utils import wants_json

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
        "motivated": args.get("motivated") or None,
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


def _back():
    return redirect(safe_next_url(request.form.get("next")) or url_for("absences.index"))


def _action_done(absence, message):
    """Answer a revoke/extend/motivated action.

    fetch() gets JSON with the re-rendered row; a plain form post redirects back.
    """
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
            "motivated": absence.motivated,
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


@bp.post("/<int:absence_id>/motivated")
@staff_required
def motivated(absence_id):
    """Tick or untick "motivated". The form sends the new value: motivated=1 or 0."""
    absence = _absence_or_404(absence_id)
    value = request.form.get("motivated") == "1"
    try:
        service.set_motivated(absence, value)
    except service.AbsenceError as e:
        return _action_failed(e)
    state = "motivated" if value else "not motivated"
    return _action_done(absence, f"Absence of {absence.student.full_name} marked {state}.")
