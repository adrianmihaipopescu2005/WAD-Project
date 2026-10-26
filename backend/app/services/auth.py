from urllib.parse import urlsplit

from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import User

# Checked when the email is unknown, so both failure cases take the same time.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def normalize_email(email):
    return email.strip().lower()


def authenticate(email, password):
    """Return the user for these credentials, or None."""
    user = db.session.execute(
        db.select(User).filter_by(email=normalize_email(email))
    ).scalar_one_or_none()
    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        return None
    return user if user.check_password(password) else None


def safe_next_url(target):
    """Only allow same-site relative paths as a post-login redirect (prevents open redirects)."""
    # Browsers treat "\" like "/", so "/\evil.com" would act as "//evil.com".
    if not target or "\\" in target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target
