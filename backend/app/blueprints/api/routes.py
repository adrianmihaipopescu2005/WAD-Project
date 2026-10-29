from flask import Blueprint, request
from flask_login import current_user

from ...services import validation as service

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def _api_user():
    """The caller: the X-API-Key owner, else the logged-in user (dashboard widget), else None.

    A key that is sent but invalid is rejected, even if there is also a login session.
    """
    if "X-API-Key" in request.headers:
        return service.user_for_key(request.headers["X-API-Key"])
    return current_user if current_user.is_authenticated else None


@bp.get("/validate")
def validate():
    """GET /api/v1/validate?student_id=…&date=YYYY-MM-DD → is the student excused?"""
    user = _api_user()
    if user is None:
        return {"error": "Send a valid X-API-Key header, or log in."}, 401
    if not user.is_staff:
        return {"error": "Only staff can use the validation API."}, 403
    try:
        student_id = service.parse_student_id(request.args.get("student_id"))
        day = service.parse_day(request.args.get("date"))
        return service.check_excused(user, student_id, day)
    except service.ValidationError as e:
        return {"error": str(e)}, e.status
