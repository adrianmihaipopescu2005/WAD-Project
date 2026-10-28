from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ...decorators import staff_required
from ...models import DECISIONS, SLOTS
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
        "decision": args.get("decision") or None,
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
        decisions=DECISIONS,
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


def _action_done(absence, message, category="success"):
    """Answer a revoke/extend/motivated action.

    fetch() gets JSON with the re-rendered row; a plain form post redirects back.
    """
    if not wants_json():
        flash(message, category)
        return _back()
    row = render_template(
        "absences/_row.html",
        a=absence,
        show_student=request.form.get("show_student") == "1",
        next_url=safe_next_url(request.form.get("next")) or url_for("absences.index"),
    )
    return {
        "message": message,
        "category": category,
        "absence": {
            "id": absence.id,
            "status": absence.status,
            "decision": absence.decision,
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


@bp.post("/<int:absence_id>/decision")
@staff_required
def decision(absence_id):
    """Motivated / not motivated. Saves the decision, then emails the student."""
    absence = _absence_or_404(absence_id)
    try:
        sent = service.decide(absence, request.form.get("decision"), current_user)
    except service.AbsenceError as e:
        return _action_failed(e)
    name = absence.student.name
    label = absence.decision_label.lower()
    if sent:
        return _action_done(absence, f"{name}: {label}. Email sent to {absence.email}.")
    return _action_done(
        absence,
        f"{name}: {label}, but the email to {absence.email} couldn't be sent. "
        "Click the same button again later to retry.",
        "warning",
    )
