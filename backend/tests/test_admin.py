import pytest
from conftest import TUESDAY, add_student, login

from app.models import ROLE_ASSISTANT, Absence, Student, User
from app.services import assistants as service


def _add_student(db, assistant, name):
    """A student in their own team, so each call adds one team."""
    return add_student(assistant, name)


def _get(db, model, id_):
    db.session.expire_all()
    return db.session.get(model, id_)


@pytest.fixture
def admin_client(client, admin):
    login(client, admin.email)
    return client


# --- access control -----------------------------------------------------------------

@pytest.mark.parametrize(
    ("method", "url"),
    [("get", "/admin/assistants"), ("get", "/admin/assistants/new"),
     ("post", "/admin/assistants/new"), ("post", "/admin/assistants/1/delete")],
)
def test_assistant_gets_403(client, assistant, method, url):
    login(client, assistant.email)
    assert getattr(client, method)(url).status_code == 403


@pytest.mark.parametrize("url", ["/admin/assistants", "/admin/assistants/new"])
def test_anonymous_redirected_to_login(client, url):
    res = client.get(url)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_navbar_assistants_link_only_for_admin(client, admin, assistant):
    login(client, assistant.email)
    assert 'href="/admin/assistants"' not in client.get("/dashboard/").get_data(as_text=True)
    client.post("/logout")
    login(client, admin.email)
    assert 'href="/admin/assistants"' in client.get("/dashboard/").get_data(as_text=True)


# --- list ---------------------------------------------------------------------------

def test_list_empty_state(admin_client):
    assert "No lab assistants yet" in admin_client.get("/admin/assistants").get_data(as_text=True)


def test_list_shows_assistants_with_team_counts(admin_client, db, admin, assistant, make_user):
    other = make_user("other@example.com", ROLE_ASSISTANT)
    _add_student(db, assistant, "S1")
    _add_student(db, assistant, "S2")
    html = admin_client.get("/admin/assistants").get_data(as_text=True)
    assert assistant.email in html and other.email in html
    assert admin.email not in html  # admins are not listed as assistants
    assert f'data-teams="{assistant.id}">2<' in html
    assert f'data-teams="{other.id}">0<' in html


# --- create -------------------------------------------------------------------------

def test_create_assistant(admin_client, db):
    res = admin_client.post("/admin/assistants/new", data={
        "name": " Ion Ionescu ", "email": "Ion@UPT.ro", "password": "temp-pass-1",
    })
    assert res.status_code == 302
    user = db.session.execute(db.select(User).filter_by(email="ion@upt.ro")).scalar_one()
    assert user.role == ROLE_ASSISTANT
    assert user.name == "Ion Ionescu"
    assert user.check_password("temp-pass-1")

    admin_client.post("/logout")
    assert login(admin_client, "ion@upt.ro", "temp-pass-1").status_code == 302


@pytest.mark.parametrize(
    "email", ["assistant@example.com", "ASSISTANT@example.com", "prof@example.com"]
)
def test_create_duplicate_email_rejected(admin_client, db, assistant, email):
    res = admin_client.post("/admin/assistants/new", data={
        "name": "Dup", "email": email, "password": "temp-pass-1",
    })
    assert res.status_code == 200
    assert "already exists" in res.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count(User.id))) == 2


@pytest.mark.parametrize(
    ("data", "message"),
    [({"name": "A", "email": "not-an-email", "password": "temp-pass-1"}, "valid email"),
     ({"name": "A", "email": "a@b.ro", "password": "short"}, "at least 8"),
     ({"name": "", "email": "a@b.ro", "password": "temp-pass-1"}, "is-invalid")],
)
def test_create_validation(admin_client, db, data, message):
    res = admin_client.post("/admin/assistants/new", data=data)
    assert res.status_code == 200
    assert message in res.get_data(as_text=True)
    assert db.session.execute(db.select(User).filter_by(role=ROLE_ASSISTANT)).first() is None


# --- remove -------------------------------------------------------------------------

def test_remove_assistant_without_teams(admin_client, db, assistant):
    res = admin_client.post(f"/admin/assistants/{assistant.id}/delete")
    assert res.status_code == 302
    assert _get(db, User, assistant.id) is None


def test_remove_with_teams_requires_target(admin_client, db, assistant, make_user):
    make_user("other@example.com", ROLE_ASSISTANT)
    _add_student(db, assistant, "S1")
    res = admin_client.post(f"/admin/assistants/{assistant.id}/delete", follow_redirects=True)
    assert "Choose another assistant" in res.get_data(as_text=True)
    assert _get(db, User, assistant.id) is not None


def test_remove_reassigns_teams_and_keeps_absences(admin_client, db, assistant, make_user):
    other = make_user("other@example.com", ROLE_ASSISTANT)
    s1 = _add_student(db, assistant, "S1")
    s2 = _add_student(db, assistant, "S2")
    db.session.add(Absence(student=s1, slot="TUE_18_20", start_date=TUESDAY, reason="Doctor"))
    db.session.commit()
    assistant_id, other_id = assistant.id, other.id

    res = admin_client.post(
        f"/admin/assistants/{assistant_id}/delete",
        data={"reassign_to": other_id}, follow_redirects=True,
    )
    assert "were moved to" in res.get_data(as_text=True)
    assert _get(db, User, assistant_id) is None
    assert _get(db, Student, s1.id).team.assistant_id == other_id
    assert _get(db, Student, s2.id).team.assistant_id == other_id
    assert len(_get(db, Student, s1.id).absences) == 1


@pytest.mark.parametrize("target", ["self", "admin", "missing"])
def test_remove_invalid_target_rejected(admin_client, db, admin, assistant, target):
    _add_student(db, assistant, "S1")
    target_id = {"self": assistant.id, "admin": admin.id, "missing": 999}[target]
    admin_client.post(f"/admin/assistants/{assistant.id}/delete", data={"reassign_to": target_id})
    assert _get(db, User, assistant.id) is not None
    assert _get(db, Student, 1).team.assistant_id == assistant.id


def test_remove_admin_or_missing_is_404(admin_client, admin):
    assert admin_client.post(f"/admin/assistants/{admin.id}/delete").status_code == 404
    assert admin_client.post("/admin/assistants/999/delete").status_code == 404


def test_remove_is_atomic(app, db, assistant, make_user, monkeypatch):
    other = make_user("other@example.com", ROLE_ASSISTANT)
    s = _add_student(db, assistant, "S1")

    def boom(_obj):
        raise RuntimeError("simulated failure after the reassignment UPDATE")

    monkeypatch.setattr(db.session, "delete", boom)
    with pytest.raises(RuntimeError):
        service.remove_assistant(assistant, other)
    monkeypatch.undo()

    assert _get(db, User, assistant.id) is not None
    assert _get(db, Student, s.id).team.assistant_id == assistant.id  # UPDATE was rolled back


def test_remove_modal_offers_only_other_assistants(admin_client, db, assistant, make_user):
    other = make_user("other@example.com", ROLE_ASSISTANT)
    _add_student(db, assistant, "S1")
    html = admin_client.get("/admin/assistants").get_data(as_text=True)
    modal = html.split(f'id="remove-{assistant.id}"')[1].split("</form>")[0]
    assert f'<option value="{other.id}">' in modal
    assert f'<option value="{assistant.id}">' not in modal


def test_remove_disabled_when_no_other_assistant(admin_client, db, assistant):
    _add_student(db, assistant, "S1")
    html = admin_client.get("/admin/assistants").get_data(as_text=True)
    assert "no other" in html and "assistant to take them over" in html
