from flask import Blueprint, redirect, render_template, request, session, url_for

from ...models import SLOTS
from ...services import absences as service
from .forms import PublicAbsenceForm

bp = Blueprint("public", __name__, url_prefix="/report")


@bp.route("/", methods=["GET", "POST"])
def report():
    """Students report an absence without logging in."""
    form = PublicAbsenceForm()
    if form.validate_on_submit():
        try:
            absence = service.submit_public(
                form.student_number.data, form.slot.data, form.start_date.data,
                form.sessions_count.data, form.reason.data,
            )
        except service.AbsenceError as e:
            field = form.student_number if e.status == 404 else form.start_date
            field.errors.append(str(e))
        else:
            # Shown once on the confirmation page. Initials only, like the lookup.
            session["last_report"] = {
                "initials": service.public_lookup(absence.student.student_number)["initials"],
                "slot": absence.slot_label,
                "start": absence.start_date.isoformat(),
                "end": absence.end_date.isoformat(),
                "sessions": absence.sessions_count,
            }
            return redirect(url_for("public.thanks"))
    return render_template("public/report.html", form=form, slots=SLOTS)


@bp.get("/thanks")
def thanks():
    summary = session.pop("last_report", None)
    if summary is None:
        return redirect(url_for("public.report"))
    return render_template("public/thanks.html", summary=summary)


@bp.get("/lookup.json")
def lookup():
    """Smart form: confirms a student number while typing. Reveals initials and group only."""
    return service.public_lookup(request.args.get("student_number", ""))
