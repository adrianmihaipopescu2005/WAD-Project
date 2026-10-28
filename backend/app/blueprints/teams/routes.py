from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from ...decorators import staff_required
from ...models import SLOTS
from ...services import teams as service
from ...services.assistants import list_assistants
from .forms import TeamForm

bp = Blueprint("teams", __name__)


def _team_or_404(team_id):
    return service.get_team(current_user, team_id) or abort(404)


def _build_form(team=None):
    form = TeamForm(obj=team)
    if team is not None and request.method == "GET":
        names = [m.name for m in team.members] + ["", ""]
        form.member_1.data, form.member_2.data = names[:2]
    if current_user.is_admin:
        form.assistant_id.choices = [(a.id, a.name) for a, _count in list_assistants()]
    else:
        del form.assistant_id
    return form


def _list_filters():
    assistant_id = request.args.get("assistant", type=int) if current_user.is_admin else None
    return assistant_id, request.args.get("q", "").strip(), request.args.get("slot") or None


def _list_context():
    assistant_id, q, slot = _list_filters()
    return {
        "teams": service.list_teams(current_user, assistant_id, q, slot),
        "filtered": bool(q or assistant_id or slot),
    }


@bp.get("/teams/")
@staff_required
def index():
    assistant_id, q, slot = _list_filters()
    return render_template(
        "teams/list.html",
        assistants=list_assistants() if current_user.is_admin else [],
        selected_assistant=assistant_id, q=q, selected_slot=slot, slots=SLOTS,
        **_list_context(),
    )


@bp.get("/teams/search.json")
@staff_required
def search():
    """Live search: the same filters as the page, returning the rendered results."""
    ctx = _list_context()
    return {"count": len(ctx["teams"]), "html": render_template("teams/_results.html", **ctx)}


@bp.route("/teams/new", methods=["GET", "POST"])
@staff_required
def new():
    form = _build_form()
    if current_user.is_admin and not form.assistant_id.choices:
        flash("Add a lab assistant before adding teams.", "warning")
        return redirect(url_for("admin.assistants"))

    if form.validate_on_submit():
        owner = form.assistant_id.data if current_user.is_admin else current_user.id
        try:
            team = service.create_team(
                owner, form.slot.data, [form.member_1.data, form.member_2.data]
            )
        except service.TeamError as e:
            form.member_1.errors.append(str(e))
        else:
            flash(f"Team {team.label} added.", "success")
            return redirect(url_for("teams.index"))
    return render_template("teams/form.html", form=form, team=None)


@bp.route("/teams/<int:team_id>/edit", methods=["GET", "POST"])
@staff_required
def edit(team_id):
    team = _team_or_404(team_id)
    form = _build_form(team)
    if form.validate_on_submit():
        owner = form.assistant_id.data if current_user.is_admin else None
        try:
            service.update_team(
                team, form.slot.data, [form.member_1.data, form.member_2.data], owner
            )
        except service.TeamError as e:
            form.member_1.errors.append(str(e))
        else:
            flash(f"Team {team.label} updated.", "success")
            return redirect(url_for("teams.index"))
    return render_template(
        "teams/form.html", form=form, team=team, delete_form=FlaskForm(),
    )


@bp.post("/teams/<int:team_id>/delete")
@staff_required
def delete(team_id):
    team = _team_or_404(team_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    label = team.label
    service.delete_team(team)
    flash(f"Team {label} was deleted, with its students' absences.", "success")
    return redirect(url_for("teams.index"))


@bp.get("/students/<int:student_id>")
@staff_required
def profile(student_id):
    student = service.get_student(current_user, student_id) or abort(404)
    absences = sorted(student.absences, key=lambda a: (a.start_date, a.id), reverse=True)
    return render_template(
        "teams/profile.html", student=student, absences=absences,
        next_url=url_for("teams.profile", student_id=student.id),
    )
