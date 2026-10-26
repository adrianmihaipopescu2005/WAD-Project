from datetime import UTC, date, datetime, timedelta

from flask_login import UserMixin
from sqlalchemy import CheckConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

ROLE_ADMIN = "admin"
ROLE_ASSISTANT = "assistant"

# Slot code → (label, Python weekday where Monday = 0).
SLOTS = {
    "TUE_18_20": ("Tuesday 18–20", 1),
    "THU_18_20": ("Thursday 18–20", 3),
}

# One semester has 14 weekly sessions per slot.
MAX_SESSIONS = 14

# An absence may start at most this many days before / after today (decided 2026-10-26).
DAYS_BACK = 30
DAYS_AHEAD = 183

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"

SOURCE_PUBLIC = "public"
SOURCE_ASSISTANT = "assistant"


def _now():
    return datetime.now(UTC)


class User(UserMixin, db.Model):
    """A logged-in user: the professor (admin) or a lab assistant (WAD "seller")."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN ('{ROLE_ADMIN}', '{ROLE_ASSISTANT}')", name="ck_users_role"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_ASSISTANT)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    students = db.relationship("Student", back_populates="assistant")
    api_key = db.relationship(
        "ApiKey", back_populates="user", uselist=False,
        cascade="all, delete-orphan", passive_deletes=True,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN


class Student(db.Model):
    """A student (WAD "customer"). Belongs to exactly one assistant and has no login."""

    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    assistant_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    student_number = db.Column(db.String(32), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255))
    study_group = db.Column(db.String(32))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    assistant = db.relationship("User", back_populates="students")
    absences = db.relationship(
        "Absence", back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Absence(db.Model):
    """An absence report (WAD "license"). Covers `sessions_count` weekly sessions of one slot."""

    __tablename__ = "absences"
    __table_args__ = (
        CheckConstraint(
            "slot IN (" + ", ".join(f"'{s}'" for s in SLOTS) + ")", name="ck_absences_slot"
        ),
        # SQLite strftime('%w'): Sunday = 0, so Tuesday = 2 and Thursday = 4.
        CheckConstraint(
            "(slot = 'TUE_18_20' AND strftime('%w', start_date) = '2')"
            " OR (slot = 'THU_18_20' AND strftime('%w', start_date) = '4')",
            name="ck_absences_slot_weekday",
        ),
        CheckConstraint("sessions_count >= 1", name="ck_absences_sessions_count"),
        CheckConstraint(
            f"status IN ('{STATUS_ACTIVE}', '{STATUS_REVOKED}')", name="ck_absences_status"
        ),
        CheckConstraint(
            f"source IN ('{SOURCE_PUBLIC}', '{SOURCE_ASSISTANT}')", name="ck_absences_source"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot = db.Column(db.String(16), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    sessions_count = db.Column(db.Integer, nullable=False, default=1)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default=STATUS_ACTIVE)
    source = db.Column(db.String(16), nullable=False, default=SOURCE_ASSISTANT)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    revoked_at = db.Column(db.DateTime(timezone=True))

    student = db.relationship("Student", back_populates="absences")

    @property
    def slot_label(self):
        return SLOTS[self.slot][0]

    @property
    def end_date(self):
        """Date of the last lab session this absence covers."""
        return self.start_date + timedelta(weeks=self.sessions_count - 1)

    def covers(self, day: date) -> bool:
        """True if this absence excuses the student from the lab session on `day`."""
        if self.status != STATUS_ACTIVE or day.weekday() != SLOTS[self.slot][1]:
            return False
        weeks = (day - self.start_date).days // 7
        return 0 <= weeks < self.sessions_count


class ApiKey(db.Model):
    """A user's key for the validation API. Only a SHA-256 hash of the key is stored."""

    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    key_hash = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    last_used_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="api_key")
