from functools import wraps

from flask import abort
from flask_login import current_user

from .extensions import login_manager
from .models import ROLE_ADMIN, ROLE_ASSISTANT
from .utils import wants_json


def role_required(*roles):
    """Anonymous users go to the login page. Logged-in users without one of `roles` get 403."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                if wants_json():  # fetch() can't follow a redirect to the login page usefully
                    return {"error": "Your session has expired. Log in again."}, 401
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


admin_required = role_required(ROLE_ADMIN)
staff_required = role_required(ROLE_ADMIN, ROLE_ASSISTANT)
