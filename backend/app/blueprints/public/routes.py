from flask import Blueprint, redirect, render_template, session, url_for

from ...models import SLOTS
from ...ratelimit import rate_limit
from ...services import absences as service
from .forms import PublicAbsenceForm

bp = Blueprint("public", __name__, url_prefix="/report")


@bp.route("/", methods=["GET", "POST"])
@rate_limit("report", limit=10, methods=("POST",))
def report():
    """Students report an absence without logging in: pick the team, then their own name."""
    teams = service.public_teams()
    form = PublicAbsenceForm()
    form.student_id.choices = [(m.id, m.name) for t in teams for m in t.members]
    if form.validate_on_submit():
        try:
            absence = service.submit_public(
                form.student_id.data, form.start_date.data, form.reason.data,
            )
        except service.AbsenceError as e:
            field = form.student_id if e.status == 404 else form.start_date
            field.errors.append(str(e))
        else:
            # Shown once on the confirmation page.
            session["last_report"] = {
                "name": absence.student.name,
                "slot": absence.slot_label,
                "date": absence.start_date.isoformat(),
            }
            return redirect(url_for("public.thanks"))
    return render_template("public/report.html", form=form, teams=teams, slots=SLOTS)


@bp.get("/thanks")
def thanks():
    summary = session.pop("last_report", None)
    if summary is None:
        return redirect(url_for("public.report"))
    return render_template("public/thanks.html", summary=summary)
