"""In-place upgrades of an existing SQLite database (used by `flask upgrade-db`)."""

from sqlalchemy.schema import CreateTable

from .extensions import db
from .models import ROLE_STUDENT, User


def upgrade_users_role_check():
    """Rebuild `users` so its role CHECK allows students. Returns False if nothing to do.

    SQLite can't change a CHECK constraint in place, so this is the documented table rebuild:
    with foreign keys off, copy into a new table, swap it in, check every FK, in one transaction.
    """
    db.session.remove()
    columns = ", ".join(c.name for c in User.__table__.columns)
    create = str(CreateTable(User.__table__).compile(db.engine)).replace(
        "CREATE TABLE users", "CREATE TABLE users_new", 1
    )

    # The raw sqlite3 connection: PRAGMA foreign_keys only works outside a transaction, and
    # SQLAlchemy would have opened one already.
    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        sql = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if sql is None or f"'{ROLE_STUDENT}'" in sql[0]:
            return False

        conn.commit()
        cursor.execute("PRAGMA foreign_keys=OFF")
        try:
            cursor.execute("BEGIN")
            cursor.execute(create)
            cursor.execute(f"INSERT INTO users_new ({columns}) SELECT {columns} FROM users")
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")
            broken = cursor.execute("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"Foreign key check failed after the upgrade: {broken}")
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
        finally:
            cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        conn.close()
    return True
