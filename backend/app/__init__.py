import secrets
from pathlib import Path

import click
from flask import Flask, render_template, request

from .config import Config
from .extensions import csrf, db, login_manager
from .models import MAX_SESSIONS, ROLE_ADMIN, ROLE_ASSISTANT, User
from .services.absences import date_window
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
    _ensure_secret_key(app)

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
    from .blueprints.api.routes import bp as api_bp
    from .blueprints.auth.forms import LogoutForm
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.dashboard.routes import bp as dashboard_bp
    from .blueprints.main.routes import bp as main_bp
    from .blueprints.public.routes import bp as public_bp
    from .blueprints.teams.routes import bp as teams_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(absences_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)

    # logout_form: the navbar's logout button is a POST form on every page.
    # date_window: min/max for the date pickers (the server enforces the same window).
    app.context_processor(lambda: {
        "logout_form": LogoutForm(), "max_sessions": MAX_SESSIONS, "date_window": date_window,
    })

    _register_error_handlers(app)
    _register_cli(app)
    return app


def _ensure_secret_key(app):
    """Never sign sessions with a public default key outside debug/testing."""
    if app.config.get("SECRET_KEY"):
        return
    if app.debug or app.testing:
        app.config["SECRET_KEY"] = "dev-only-insecure-key"
    else:
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY is not set: using a random key, so logins end on restart.")


ERROR_TITLES = {
    400: "Bad request",
    405: "Method not allowed",
    429: "Too many requests",
    500: "Something went wrong",
}


def _register_error_handlers(app):
    def handle(e):
        # fetch() calls and every /api/ route get JSON errors.
        if wants_json() or request.path.startswith("/api/"):
            return {"error": e.description}, e.code
        if e.code in (403, 404):
            return render_template(f"errors/{e.code}.html"), e.code
        return render_template(
            "errors/error.html", code=e.code, title=ERROR_TITLES.get(e.code, "Error"),
            message=e.description if e.code != 500 else "Please try again later.",
        ), e.code

    # 400 also covers CSRFError (a BadRequest subclass).
    for code in (400, 403, 404, 405, 429, 500):
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

    @app.cli.command("seed-demo")
    @click.option("--reset", is_flag=True, help="Delete ALL existing data first.")
    def seed_demo_command(reset):
        """Fill an empty database with demo users, teams and absences."""
        from .seed import ADMIN, ASSISTANTS, seed_demo

        if reset:
            click.confirm("This deletes ALL users, teams and absences. Continue?", abort=True)
            db.drop_all()
        db.create_all()
        if db.session.execute(db.select(User.id).limit(1)).first() is not None:
            raise click.ClickException(
                "The database already has users. Use --reset to replace everything with demo data."
            )
        seed_demo()
        click.echo("Demo data created. Log in with:")
        click.echo(f"  admin:     {ADMIN[0]} / {ADMIN[2]}")
        for email, _name, password in ASSISTANTS:
            click.echo(f"  assistant: {email} / {password}")
        click.echo("Demo teams are ready on the public form (/report/).")

    @app.cli.command("import-teams")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--assistant", "assistant_email",
                  help="Email of the lab assistant who gets the teams. "
                       "Optional when there is exactly one assistant.")
    def import_teams_command(path, assistant_email):
        """Create teams from a text file: a 'Tuesday:'/'Thursday:' line, then one team per line
        with the two names separated by '|', a tab or two spaces. Safe to run twice."""
        from .services.teams import TeamError, import_teams

        db.create_all()
        stmt = db.select(User).where(User.role == ROLE_ASSISTANT)
        if assistant_email:
            stmt = stmt.where(User.email == normalize_email(assistant_email))
        assistants = db.session.execute(stmt).scalars().all()
        if len(assistants) != 1:
            raise click.ClickException(
                "No lab assistant with that email." if assistant_email else
                "Pass --assistant EMAIL (there isn't exactly one lab assistant)."
            )
        with open(path, encoding="utf-8") as f:
            text = f.read()
        try:
            created, skipped = import_teams(assistants[0], text)
        except TeamError as e:
            raise click.ClickException(f"{e} Nothing was imported.") from None
        click.echo(f"Imported {created} team(s) for {assistants[0].name}; "
                   f"skipped {skipped} already there.")
