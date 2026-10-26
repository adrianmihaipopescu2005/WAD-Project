from ..extensions import db
from ..models import STATUS_ACTIVE, Absence, Student


class StudentError(Exception):
    """A rule violation the user should see as a form error."""


def _visible_to(stmt, user):
    """Restrict a Student query to what `user` may see. Admins see everyone."""
    return stmt if user.is_admin else stmt.where(Student.assistant_id == user.id)


def search_clause(q):
    """WHERE clause matching a student's number, first, last or full name (case-insensitive)."""
    pattern = f"%{q.strip()}%"
    return db.or_(
        Student.student_number.ilike(pattern),
        Student.first_name.ilike(pattern),
        Student.last_name.ilike(pattern),
        (Student.first_name + " " + Student.last_name).ilike(pattern),
    )


def visible_students(user):
    """All students `user` may see, ordered by name (for select boxes)."""
    stmt = _visible_to(db.select(Student), user).order_by(Student.last_name, Student.first_name)
    return db.session.execute(stmt).scalars().all()


def list_students(user, assistant_id=None, q=None):
    """Students visible to `user`, each with their count of active absences."""
    active = (
        db.select(db.func.count(Absence.id))
        .where(Absence.student_id == Student.id, Absence.status == STATUS_ACTIVE)
        .scalar_subquery()
    )
    stmt = _visible_to(db.select(Student, active), user)
    if user.is_admin and assistant_id:
        stmt = stmt.where(Student.assistant_id == assistant_id)
    if q:
        stmt = stmt.where(search_clause(q))
    stmt = stmt.order_by(Student.last_name, Student.first_name)
    return db.session.execute(stmt).all()


def get_student(user, student_id):
    """The student, or None if it doesn't exist or `user` may not see it."""
    stmt = _visible_to(db.select(Student).where(Student.id == student_id), user)
    return db.session.execute(stmt).scalar_one_or_none()


def _number_taken(number, exclude_id=None):
    stmt = db.select(Student.id).where(Student.student_number == number)
    if exclude_id is not None:
        stmt = stmt.where(Student.id != exclude_id)
    return db.session.execute(stmt).first() is not None


def _apply(student, data):
    student.student_number = data["student_number"].strip()
    student.first_name = data["first_name"].strip()
    student.last_name = data["last_name"].strip()
    student.email = (data.get("email") or "").strip().lower() or None
    student.study_group = (data.get("study_group") or "").strip() or None


def create_student(assistant_id, data):
    if _number_taken(data["student_number"].strip()):
        raise StudentError("A student with this student number already exists.")
    student = Student(assistant_id=assistant_id)
    _apply(student, data)
    db.session.add(student)
    db.session.commit()
    return student


def update_student(student, data, assistant_id=None):
    """`assistant_id` reassigns the student (admins only; the route enforces that)."""
    if _number_taken(data["student_number"].strip(), exclude_id=student.id):
        raise StudentError("A student with this student number already exists.")
    _apply(student, data)
    if assistant_id is not None:
        student.assistant_id = assistant_id
    db.session.commit()
    return student


def delete_student(student):
    """Delete the student. Their absences are deleted with them (FK ON DELETE CASCADE)."""
    db.session.delete(student)
    db.session.commit()
