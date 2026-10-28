from flask import Blueprint, abort, flash, redirect, render_template, url_for

from ...decorators import admin_required
from ...services import assistants as service
from .forms import AssistantForm, RemoveAssistantForm

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/assistants")
@admin_required
def assistants():
    return render_template("admin/assistants.html", assistants=service.list_assistants())


@bp.route("/assistants/new", methods=["GET", "POST"])
@admin_required
def new_assistant():
    form = AssistantForm()
    if form.validate_on_submit():
        try:
            user = service.create_assistant(form.name.data, form.email.data, form.password.data)
        except service.AssistantError as e:
            form.email.errors.append(str(e))
        else:
            flash(f"Lab assistant {user.name} added.", "success")
            return redirect(url_for("admin.assistants"))
    return render_template("admin/assistant_form.html", form=form)


@bp.post("/assistants/<int:assistant_id>/delete")
@admin_required
def delete_assistant(assistant_id):
    assistant = service.get_assistant(assistant_id) or abort(404)
    form = RemoveAssistantForm()
    if not form.validate_on_submit():
        abort(400)

    target = None
    if form.reassign_to.data is not None:
        target = service.get_assistant(form.reassign_to.data)
        if target is None:
            flash("The selected assistant doesn't exist.", "danger")
            return redirect(url_for("admin.assistants"))

    try:
        service.remove_assistant(assistant, target)
    except service.AssistantError as e:
        flash(str(e), "danger")
    else:
        moved = f" Their teams were moved to {target.name}." if target else ""
        flash(f"Lab assistant {assistant.name} removed.{moved}", "success")
    return redirect(url_for("admin.assistants"))
