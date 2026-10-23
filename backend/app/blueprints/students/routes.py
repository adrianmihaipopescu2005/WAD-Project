from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf import FlaskForm

from ...decorators import staff_required
from ...services import students as service
from ...services.assistants import list_assistants
from .forms import StudentForm

bp = Blueprint("students", __name__, url_prefix="/students")


def _student_or_404(student_id):
    return service.get_student(current_user, student_id) or abort(404)


def _build_form(**kwargs):
    form = StudentForm(**kwargs)
    if current_user.is_admin:
        form.assistant_id.choices = [(a.id, a.name) for a, _count in list_assistants()]
    else:
        del form.assistant_id
    return form


def _form_data(form):
    return {name: getattr(form, name).data for name in
            ("student_number", "first_name", "last_name", "email", "study_group")}


@bp.get("/")
@staff_required
def index():
    assistant_id = request.args.get("assistant", type=int)
    q = request.args.get("q", "").strip()
    return render_template(
        "students/list.html",
        students=service.list_students(current_user, assistant_id, q),
        assistants=list_assistants() if current_user.is_admin else [],
        selected_assistant=assistant_id,
        q=q,
    )


@bp.route("/new", methods=["GET", "POST"])
@staff_required
def new():
    form = _build_form()
    if current_user.is_admin and not form.assistant_id.choices:
        flash("Add a lab assistant before adding students.", "warning")
        return redirect(url_for("admin.assistants"))

    if form.validate_on_submit():
        owner = form.assistant_id.data if current_user.is_admin else current_user.id
        try:
            student = service.create_student(owner, _form_data(form))
        except service.StudentError as e:
            form.student_number.errors.append(str(e))
        else:
            flash(f"Student {student.full_name} added.", "success")
            return redirect(url_for("students.profile", student_id=student.id))
    return render_template("students/form.html", form=form, student=None)


@bp.get("/<int:student_id>")
@staff_required
def profile(student_id):
    student = _student_or_404(student_id)
    absences = sorted(student.absences, key=lambda a: a.start_date, reverse=True)
    return render_template(
        "students/profile.html", student=student, absences=absences, delete_form=FlaskForm()
    )


@bp.route("/<int:student_id>/edit", methods=["GET", "POST"])
@staff_required
def edit(student_id):
    student = _student_or_404(student_id)
    form = _build_form(obj=student)
    if form.validate_on_submit():
        owner = form.assistant_id.data if current_user.is_admin else None
        try:
            service.update_student(student, _form_data(form), owner)
        except service.StudentError as e:
            form.student_number.errors.append(str(e))
        else:
            flash(f"Student {student.full_name} updated.", "success")
            return redirect(url_for("students.profile", student_id=student.id))
    return render_template("students/form.html", form=form, student=student)


@bp.post("/<int:student_id>/delete")
@staff_required
def delete(student_id):
    student = _student_or_404(student_id)
    if not FlaskForm().validate_on_submit():
        abort(400)
    name = student.full_name
    service.delete_student(student)
    flash(f"Student {name} and their absences were deleted.", "success")
    return redirect(url_for("students.index"))
