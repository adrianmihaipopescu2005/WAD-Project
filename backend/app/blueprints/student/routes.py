from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user

from ...decorators import student_required
from ...models import DECISIONS
from ...ratelimit import rate_limit
from ...services import student_accounts as service
from ..auth.routes import home_url
from .forms import AccountLinkForm, SetPasswordForm

bp = Blueprint("student", __name__)


@bp.route("/signup", methods=["GET", "POST"])
@rate_limit("signup", limit=5, methods=("POST",))
def signup():
    """Create an account or reset a forgotten password: both start with an emailed link."""
    if current_user.is_authenticated:
        return redirect(home_url(current_user))
    form = AccountLinkForm()
    if form.validate_on_submit():
        service.request_link(form.name.data, form.email.data)
        # The same answer whether or not the email has an account.
        return render_template("student/link_sent.html", email=form.email.data)
    return render_template("student/signup.html", form=form)


@bp.route("/signup/<token>", methods=["GET", "POST"])
def set_password(token):
    try:
        link = service.read_link(token)
    except service.AccountError as e:
        return render_template("student/link_invalid.html", message=str(e)), 400
    form = SetPasswordForm()
    if form.validate_on_submit():
        try:
            user = service.set_password(token, form.password.data)
        except service.AccountError as e:
            return render_template("student/link_invalid.html", message=str(e)), 400
        login_user(user)
        flash("Your password is saved." if link["user"] else
              f"Welcome, {user.name}! Your account is ready.", "success")
        return redirect(url_for("student.absences"))
    return render_template("student/set_password.html", form=form, link=link)


@bp.get("/my/absences")
@student_required
def absences():
    decision = request.args.get("decision")
    decision = decision if decision in DECISIONS else None
    return render_template(
        "student/absences.html",
        absences=service.own_absences(current_user, decision),
        counts=service.decision_counts(current_user),
        decision=decision,
    )
