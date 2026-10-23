from urllib.parse import urlsplit

from ..extensions import db
from ..models import User


def normalize_email(email):
    return email.strip().lower()


def authenticate(email, password):
    """Return the user for these credentials, or None."""
    user = db.session.execute(
        db.select(User).filter_by(email=normalize_email(email))
    ).scalar_one_or_none()
    if user is None or not user.check_password(password):
        return None
    return user


def safe_next_url(target):
    """Only allow same-site relative paths as a post-login redirect (prevents open redirects)."""
    # Browsers treat "\" like "/", so "/\evil.com" would act as "//evil.com".
    if not target or "\\" in target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target
