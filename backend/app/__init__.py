from pathlib import Path

import click
from flask import Flask, render_template

from .config import Config
from .extensions import csrf, db, login_manager
from .models import MAX_SESSIONS, ROLE_ADMIN, User
from .services.auth import normalize_email
from .utils import wants_json

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_DIR / "templates"),
        static_folder=str(FRONTEND_DIR / "static"),
    )
    app.config.from_object(config_class)

    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        db_path = Path(app.instance_path) / "app.db"
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path.as_posix()}"

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    from .blueprints.absences.routes import bp as absences_bp
    from .blueprints.admin.routes import bp as admin_bp
    from .blueprints.auth.forms import LogoutForm
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.dashboard.routes import bp as dashboard_bp
    from .blueprints.main.routes import bp as main_bp
    from .blueprints.public.routes import bp as public_bp
    from .blueprints.students.routes import bp as students_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(absences_bp)
    app.register_blueprint(public_bp)

    # The navbar's logout button is a POST form on every page.
    app.context_processor(lambda: {"logout_form": LogoutForm(), "max_sessions": MAX_SESSIONS})

    _register_error_handlers(app)
    _register_cli(app)
    return app


def _register_error_handlers(app):
    def handle(e):
        if wants_json():
            return {"error": e.description}, e.code
        if e.code in (403, 404):
            return render_template(f"errors/{e.code}.html"), e.code
        return e

    # 400 also covers CSRFError (a BadRequest subclass).
    for code in (400, 403, 404, 405):
        app.register_error_handler(code, handle)


@login_manager.user_loader
def _load_user(user_id):
    return db.session.get(User, int(user_id))


def _register_cli(app):
    @app.cli.command("init-db")
    @click.option("--email", prompt=True, help="Admin (professor) email.")
    @click.option("--name", prompt=True, help="Admin display name.")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def init_db(email, name, password):
        """Create the tables and the admin account (skipped if the email already exists)."""
        db.create_all()
        email = normalize_email(email)
        if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
            click.echo(f"User {email} already exists, tables are ready.")
            return
        admin = User(email=email, name=name, role=ROLE_ADMIN)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Created admin {email}.")
