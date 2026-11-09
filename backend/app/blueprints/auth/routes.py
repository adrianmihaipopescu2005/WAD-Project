from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ...decorators import staff_required
from ...services import validation
from ...services.auth import authenticate, safe_next_url
from .forms import LoginForm, LogoutForm

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = authenticate(form.email.data, form.password.data)
        if user is not None:
            login_user(user, remember=form.remember.data)
            flash(f"Welcome, {user.name}!", "success")
            return redirect(safe_next_url(request.args.get("next")) or url_for("dashboard.index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    if LogoutForm().validate_on_submit():
        logout_user()
        flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@bp.get("/account/api-key")
@staff_required
def api_key():
    return render_template("account/api_key.html", new_key=None)


@bp.post("/account/api-key")
@staff_required
def generate_api_key():
    # Shown on this response only; it's stored hashed and can't be shown again.
    new_key = validation.generate_key(current_user)
    flash("New API key created. Copy it now: it won't be shown again.", "warning")
    response = make_response(
        render_template("account/api_key.html", new_key=new_key)
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/account/api-key/revoke")
@staff_required
def revoke_api_key():
    validation.revoke_key(current_user)
    flash("API key revoked.", "info")
    return redirect(url_for("auth.api_key"))
