from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

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
