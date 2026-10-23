from datetime import date

import pytest
from conftest import login

from app.models import ROLE_ASSISTANT, STATUS_REVOKED, Absence, Student

TUESDAY = date(2026, 10, 27)

VALID = {
    "student_number": "LM1234",
    "first_name": "Ana",
    "last_name": "Pop",
    "email": "Ana.Pop@student.upt.ro",
    "study_group": "2.1",
}


def _student(db, assistant, number, first="Ana", last="Pop"):
    s = Student(assistant=assistant, student_number=number, first_name=first, last_name=last)
    db.session.add(s)
    db.session.commit()
    return s


def _reload(db, model, id_):
    db.session.expire_all()
    return db.session.get(model, id_)


@pytest.fixture
def other(make_user):
    return make_user("other@example.com", ROLE_ASSISTANT)


@pytest.fixture
def as_assistant(client, assistant):
    login(client, assistant.email)
    return client


@pytest.fixture
def as_admin(client, admin):
    login(client, admin.email)
    return client


# --- access & scoping ---------------------------------------------------------------

@pytest.mark.parametrize("url", ["/students/", "/students/new", "/students/1", "/students/1/edit"])
def test_anonymous_redirected(client, url):
    assert "/login" in client.get(url).headers["Location"]


def test_assistant_sees_only_own_students(as_assistant, db, assistant, other):
    _student(db, assistant, "MINE1", "Mine", "One")
    _student(db, other, "THEIRS1", "Theirs", "One")
    html = as_assistant.get("/students/").get_data(as_text=True)
    assert "MINE1" in html
    assert "THEIRS1" not in html


@pytest.mark.parametrize(
    ("method", "suffix"), [("get", ""), ("get", "/edit"), ("post", "/edit"), ("post", "/delete")]
)
def test_assistant_cannot_touch_other_assistants_student(
    as_assistant, db, other, method, suffix
):
    s = _student(db, other, "THEIRS1")
    res = getattr(as_assistant, method)(f"/students/{s.id}{suffix}", data=VALID)
    assert res.status_code == 404
    assert _reload(db, Student, s.id).student_number == "THEIRS1"


def test_admin_sees_all_and_filters_by_assistant(as_admin, db, assistant, other):
    _student(db, assistant, "MINE1")
    _student(db, other, "THEIRS1")
    html = as_admin.get("/students/").get_data(as_text=True)
    assert "MINE1" in html and "THEIRS1" in html
    html = as_admin.get(f"/students/?assistant={other.id}").get_data(as_text=True)
    assert "THEIRS1" in html and "MINE1" not in html


def test_search(as_assistant, db, assistant):
    _student(db, assistant, "S1", "Ana", "Pop")
    _student(db, assistant, "S2", "Ion", "Ionescu")
    html = as_assistant.get("/students/?q=ana pop").get_data(as_text=True)
    assert "S1" in html and "S2" not in html
    html = as_assistant.get("/students/?q=s2").get_data(as_text=True)
    assert "S2" in html and ">S1<" not in html
    assert "No students match" in as_assistant.get("/students/?q=zzz").get_data(as_text=True)


def test_empty_state(as_assistant):
    assert "No students yet" in as_assistant.get("/students/").get_data(as_text=True)


def test_list_shows_active_absence_count(as_assistant, db, assistant):
    s = _student(db, assistant, "S1")
    db.session.add_all([
        Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="a"),
        Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="b", status=STATUS_REVOKED),
    ])
    db.session.commit()
    html = as_assistant.get("/students/").get_data(as_text=True)
    assert f'data-active="{s.id}">1<' in html


# --- create -------------------------------------------------------------------------

def test_assistant_creates_own_student(as_assistant, db, assistant):
    res = as_assistant.post("/students/new", data=VALID)
    assert res.status_code == 302
    s = db.session.execute(db.select(Student)).scalar_one()
    assert res.headers["Location"].endswith(f"/students/{s.id}")
    assert s.assistant_id == assistant.id
    assert s.email == "ana.pop@student.upt.ro"
    assert s.study_group == "2.1"


def test_assistant_cannot_choose_owner(as_assistant, db, assistant, other):
    as_assistant.post("/students/new", data={**VALID, "assistant_id": other.id})
    assert db.session.execute(db.select(Student)).scalar_one().assistant_id == assistant.id


def test_assistant_form_has_no_assistant_select(as_assistant):
    assert 'name="assistant_id"' not in as_assistant.get("/students/new").get_data(as_text=True)


def test_admin_creates_student_for_chosen_assistant(as_admin, db, assistant, other):
    html = as_admin.get("/students/new").get_data(as_text=True)
    assert 'name="assistant_id"' in html
    res = as_admin.post("/students/new", data={**VALID, "assistant_id": other.id})
    assert res.status_code == 302
    assert db.session.execute(db.select(Student)).scalar_one().assistant_id == other.id


def test_admin_cannot_assign_to_non_assistant(as_admin, db, admin, assistant):
    res = as_admin.post("/students/new", data={**VALID, "assistant_id": admin.id})
    assert res.status_code == 200
    assert db.session.execute(db.select(Student)).first() is None


def test_admin_without_assistants_is_redirected(as_admin):
    res = as_admin.get("/students/new")
    assert res.headers["Location"].endswith("/admin/assistants")


def test_duplicate_student_number_rejected(as_assistant, db, other):
    _student(db, other, "LM1234")  # even another assistant's student blocks the number
    res = as_assistant.post("/students/new", data=VALID)
    assert res.status_code == 200
    assert "already exists" in res.get_data(as_text=True)


@pytest.mark.parametrize(
    "override",
    [{"student_number": ""}, {"student_number": "has space"}, {"first_name": ""},
     {"last_name": ""}, {"email": "nope"}],
)
def test_create_validation(as_assistant, db, override):
    res = as_assistant.post("/students/new", data={**VALID, **override})
    assert res.status_code == 200
    assert "is-invalid" in res.get_data(as_text=True)
    assert db.session.execute(db.select(Student)).first() is None


def test_optional_fields_stored_as_null(as_assistant, db):
    as_assistant.post("/students/new", data={**VALID, "email": "", "study_group": " "})
    s = db.session.execute(db.select(Student)).scalar_one()
    assert s.email is None and s.study_group is None


# --- profile ------------------------------------------------------------------------

def test_profile_shows_details_and_absences(as_assistant, db, assistant):
    s = _student(db, assistant, "S1")
    db.session.add(
        Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, sessions_count=2, reason="Flu")
    )
    db.session.commit()
    html = as_assistant.get(f"/students/{s.id}").get_data(as_text=True)
    assert "Ana Pop" in html and "S1" in html
    assert "Tuesday 18–20" in html and "Flu" in html
    assert "2026-10-27" in html and "2026-11-03" in html  # from / until


def test_profile_empty_absences(as_assistant, db, assistant):
    s = _student(db, assistant, "S1")
    assert "No absences reported" in as_assistant.get(f"/students/{s.id}").get_data(as_text=True)


def test_profile_missing_is_404(as_assistant):
    assert as_assistant.get("/students/999").status_code == 404


# --- edit ---------------------------------------------------------------------------

def test_edit_prefills_and_updates(as_assistant, db, assistant):
    s = _student(db, assistant, "S1")
    assert 'value="S1"' in as_assistant.get(f"/students/{s.id}/edit").get_data(as_text=True)
    res = as_assistant.post(f"/students/{s.id}/edit", data={**VALID, "first_name": "Maria"})
    assert res.status_code == 302
    s = _reload(db, Student, s.id)
    assert s.first_name == "Maria" and s.student_number == "LM1234"


def test_edit_keeps_own_number(as_assistant, db, assistant):
    s = _student(db, assistant, "LM1234")
    assert as_assistant.post(f"/students/{s.id}/edit", data=VALID).status_code == 302


def test_edit_duplicate_number_rejected(as_assistant, db, assistant):
    _student(db, assistant, "LM1234")
    s = _student(db, assistant, "S2")
    res = as_assistant.post(f"/students/{s.id}/edit", data=VALID)
    assert "already exists" in res.get_data(as_text=True)
    assert _reload(db, Student, s.id).student_number == "S2"


def test_admin_can_reassign_on_edit(as_admin, db, assistant, other):
    s = _student(db, assistant, "S1")
    as_admin.post(f"/students/{s.id}/edit", data={**VALID, "assistant_id": other.id})
    assert _reload(db, Student, s.id).assistant_id == other.id


# --- delete -------------------------------------------------------------------------

def test_delete_cascades_absences(as_assistant, db, assistant):
    s = _student(db, assistant, "S1")
    db.session.add(Absence(student=s, slot="TUE_18_20", start_date=TUESDAY, reason="x"))
    db.session.commit()
    res = as_assistant.post(f"/students/{s.id}/delete")
    assert res.status_code == 302
    assert _reload(db, Student, s.id) is None
    assert db.session.execute(db.select(Absence)).first() is None


def test_delete_requires_post(as_assistant, db, assistant):
    s = _student(db, assistant, "S1")
    assert as_assistant.get(f"/students/{s.id}/delete").status_code == 405


def test_navbar_has_students_link(as_assistant):
    assert 'href="/students/"' in as_assistant.get("/dashboard/").get_data(as_text=True)
