import os


def _env_flag(name):
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


class Config:
    # Required in production. create_app uses a dev key only in debug mode.
    SECRET_KEY = os.environ.get("SECRET_KEY")
    # None → resolved to <instance>/app.db in create_app.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    # Set COOKIE_SECURE=1 when serving over HTTPS.
    SESSION_COOKIE_SECURE = _env_flag("COOKIE_SECURE")
    REMEMBER_COOKIE_SECURE = _env_flag("COOKIE_SECURE")
    RATELIMIT_ENABLED = True

    # Decision emails to students, sent over SMTP (Gmail by default: use an app password).
    # Without MAIL_USERNAME nothing is sent and staff see a warning.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_SENDER = os.environ.get("MAIL_SENDER")  # defaults to MAIL_USERNAME
    # True: keep emails in app.extensions["mail_outbox"] instead of sending (tests).
    MAIL_SUPPRESS = False


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    MAIL_SUPPRESS = True
