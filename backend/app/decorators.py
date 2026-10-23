from functools import wraps

from flask import abort
from flask_login import current_user

from .extensions import login_manager
from .models import ROLE_ADMIN


def role_required(*roles):
    """Anonymous users go to the login page. Logged-in users without one of `roles` get 403."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


admin_required = role_required(ROLE_ADMIN)
