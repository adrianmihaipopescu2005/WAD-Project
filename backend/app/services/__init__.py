from ..extensions import db


def commit_or_rollback():
    """Commit the session. On any failure, roll back so the session stays usable, then re-raise."""
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
