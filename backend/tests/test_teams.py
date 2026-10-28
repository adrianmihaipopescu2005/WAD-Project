import pytest
from conftest import TUESDAY, add_student, add_team, login

from app.models import ROLE_ASSISTANT, STATUS_REVOKED, Absence, Student, Team
from app.services.teams import TeamError, import_teams, parse_teams

VALID = {"slot": "TUE_18_20", "member_1": "Ana Pop", "member_2": "Ion Ionescu"}


def _reload(db, model, id_):
    db.session.expire_all()
    return db.session.get(model, id_)


def _names(team):
    return [m.name for m in team.members]


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

@pytest.mark.parametrize("url", ["/teams/", "/teams/new", "/teams/1/edit", "/students/1"])
def test_anonymous_redirected(client, url):
    assert "/login" in client.get(url).headers["Location"]


def test_assistant_sees_only_own_teams(as_assistant, assistant, other):
    add_team(assistant, "Mine One")
    add_team(other, "Theirs One")
    html = as_assistant.get("/teams/").get_data(as_text=True)
    assert "Mine One" in html
    assert "Theirs One" not in html


@pytest.mark.parametrize(
    ("method", "url"),
    [("get", "/teams/{t}/edit"), ("post", "/teams/{t}/edit"), ("post", "/teams/{t}/delete"),
     ("get", "/students/{s}")],
)
def test_assistant_cannot_touch_other_assistants_team(as_assistant, db, other, method, url):
    team = add_team(other, "Theirs One")
    res = getattr(as_assistant, method)(url.format(t=team.id, s=team.members[0].id), data=VALID)
    assert res.status_code == 404
    assert _names(_reload(db, Team, team.id)) == ["Theirs One"]


def test_admin_sees_all_and_filters(as_admin, assistant, other):
    add_team(assistant, "Mine One")
    add_team(other, "Theirs One", slot="THU_18_20")
    html = as_admin.get("/teams/").get_data(as_text=True)
    assert "Mine One" in html and "Theirs One" in html
    html = as_admin.get(f"/teams/?assistant={other.id}").get_data(as_text=True)
    assert "Theirs One" in html and "Mine One" not in html
    html = as_admin.get("/teams/?slot=TUE_18_20").get_data(as_text=True)
    assert "Mine One" in html and "Theirs One" not in html


def test_search_by_member_name(as_assistant, assistant):
    add_team(assistant, "Ana Pop", "Dan Stan")
    add_team(assistant, "Ion Ionescu")
    html = as_assistant.get("/teams/?q=stan").get_data(as_text=True)
    assert "Ana Pop" in html and "Ion Ionescu" not in html  # the whole team is shown
    assert "No teams match" in as_assistant.get("/teams/?q=zzz").get_data(as_text=True)


def test_search_escapes_like_wildcards(as_assistant, assistant):
    add_team(assistant, "Ana Pop")
    assert "No teams match" in as_assistant.get("/teams/?q=%25").get_data(as_text=True)


def test_empty_state(as_assistant):
    assert "No teams yet" in as_assistant.get("/teams/").get_data(as_text=True)


def test_list_shows_active_absence_count(as_assistant, db, assistant):
    team = add_team(assistant, "Ana Pop", "Ion Ionescu")
    ana, ion = team.members
    db.session.add_all([
        Absence(
            email="s@example.com", student=ana, slot="TUE_18_20", start_date=TUESDAY, reason="a"),
        Absence(
            email="s@example.com", student=ion, slot="TUE_18_20", start_date=TUESDAY, reason="b"),
        Absence(
            email="s@example.com", student=ion, slot="TUE_18_20", start_date=TUESDAY, reason="c",
                status=STATUS_REVOKED),
    ])
    db.session.commit()
    html = as_assistant.get("/teams/").get_data(as_text=True)
    assert f'data-active="{team.id}">2<' in html


# --- create -------------------------------------------------------------------------

def test_assistant_creates_own_team(as_assistant, db, assistant):
    res = as_assistant.post("/teams/new", data={**VALID, "member_1": "  Ana   Pop "})
    assert res.status_code == 302
    team = db.session.execute(db.select(Team)).scalar_one()
    assert team.assistant_id == assistant.id and team.slot == "TUE_18_20"
    assert _names(team) == ["Ana Pop", "Ion Ionescu"]  # whitespace cleaned


def test_one_person_team(as_assistant, db):
    as_assistant.post("/teams/new", data={**VALID, "member_2": ""})
    assert _names(db.session.execute(db.select(Team)).scalar_one()) == ["Ana Pop"]


def test_assistant_cannot_choose_owner(as_assistant, db, assistant, other):
    as_assistant.post("/teams/new", data={**VALID, "assistant_id": other.id})
    assert db.session.execute(db.select(Team)).scalar_one().assistant_id == assistant.id


def test_assistant_form_has_no_assistant_select(as_assistant):
    assert 'name="assistant_id"' not in as_assistant.get("/teams/new").get_data(as_text=True)


def test_admin_creates_team_for_chosen_assistant(as_admin, db, assistant, other):
    assert 'name="assistant_id"' in as_admin.get("/teams/new").get_data(as_text=True)
    res = as_admin.post("/teams/new", data={**VALID, "assistant_id": other.id})
    assert res.status_code == 302
    assert db.session.execute(db.select(Team)).scalar_one().assistant_id == other.id


def test_admin_cannot_assign_to_non_assistant(as_admin, db, admin, assistant):
    res = as_admin.post("/teams/new", data={**VALID, "assistant_id": admin.id})
    assert res.status_code == 200
    assert db.session.execute(db.select(Team)).first() is None


def test_admin_without_assistants_is_redirected(as_admin):
    assert as_admin.get("/teams/new").headers["Location"].endswith("/admin/assistants")


def test_student_in_two_teams_rejected(as_assistant, db, other):
    add_team(other, "ana pop")  # even another assistant's team blocks the name
    res = as_assistant.post("/teams/new", data=VALID)
    assert res.status_code == 200
    assert "already in another team" in res.get_data(as_text=True)
    assert db.session.execute(db.select(Team)).scalar_one().assistant_id == other.id


@pytest.mark.parametrize(
    "override",
    [{"member_1": ""}, {"member_2": "ANA POP"}, {"slot": "FRI_18_20"}, {"member_1": "x" * 161}],
)
def test_create_validation(as_assistant, db, override):
    res = as_assistant.post("/teams/new", data={**VALID, **override})
    assert res.status_code == 200
    assert "is-invalid" in res.get_data(as_text=True)
    assert db.session.execute(db.select(Team)).first() is None


# --- profile ------------------------------------------------------------------------

def test_profile_shows_team_and_absences(as_assistant, db, assistant):
    ana, ion = add_team(assistant, "Ana Pop", "Ion Ionescu").members
    db.session.add(
        Absence(
            email="s@example.com",
            student=ana, slot="TUE_18_20", start_date=TUESDAY, sessions_count=2, reason="Flu")
    )
    db.session.commit()
    html = as_assistant.get(f"/students/{ana.id}").get_data(as_text=True)
    assert "Ana Pop" in html and f'href="/students/{ion.id}">Ion Ionescu' in html
    assert "Tuesday 18–20" in html and "Flu" in html
    assert "2026-10-27" in html and "2026-11-03" in html  # from / until


def test_profile_empty_absences(as_assistant, assistant):
    s = add_student(assistant)
    assert "No absences reported" in as_assistant.get(f"/students/{s.id}").get_data(as_text=True)


def test_profile_missing_is_404(as_assistant):
    assert as_assistant.get("/students/999").status_code == 404


# --- edit ---------------------------------------------------------------------------

def test_edit_prefills_and_renames_in_place(as_assistant, db, assistant):
    team = add_team(assistant, "Ana Pop", "Ion Ionescu")
    ana_id = team.members[0].id
    db.session.add(Absence(
        email="s@example.com", student_id=ana_id, slot="TUE_18_20", start_date=TUESDAY, reason="x"))
    db.session.commit()
    html = as_assistant.get(f"/teams/{team.id}/edit").get_data(as_text=True)
    assert 'value="Ana Pop"' in html and 'value="Ion Ionescu"' in html

    res = as_assistant.post(f"/teams/{team.id}/edit", data={**VALID, "member_1": "Ana Popa"})
    assert res.status_code == 302
    student = _reload(db, Student, ana_id)
    assert student.name == "Ana Popa"
    assert len(student.absences) == 1  # the absence follows the renamed student


def test_edit_can_swap_order_and_change_slot(as_assistant, db, assistant):
    team = add_team(assistant, "Ana Pop", "Ion Ionescu")
    as_assistant.post(f"/teams/{team.id}/edit", data={
        "slot": "THU_18_20", "member_1": "Ion Ionescu", "member_2": "Ana Pop",
    })
    team = _reload(db, Team, team.id)
    assert team.slot == "THU_18_20" and _names(team) == ["Ion Ionescu", "Ana Pop"]


def test_edit_adds_and_removes_second_member(as_assistant, db, assistant):
    team = add_team(assistant, "Ana Pop")
    as_assistant.post(f"/teams/{team.id}/edit", data=VALID)
    assert _names(_reload(db, Team, team.id)) == ["Ana Pop", "Ion Ionescu"]
    as_assistant.post(f"/teams/{team.id}/edit", data={**VALID, "member_2": ""})
    assert _names(_reload(db, Team, team.id)) == ["Ana Pop"]
    assert db.session.execute(db.select(db.func.count(Student.id))).scalar() == 1


def test_admin_can_reassign_on_edit(as_admin, db, assistant, other):
    team = add_team(assistant)
    as_admin.post(f"/teams/{team.id}/edit", data={**VALID, "assistant_id": other.id})
    assert _reload(db, Team, team.id).assistant_id == other.id


# --- delete -------------------------------------------------------------------------

def test_delete_cascades_students_and_absences(as_assistant, db, assistant):
    team = add_team(assistant, "Ana Pop", "Ion Ionescu")
    db.session.add(Absence(
        email="s@example.com", student=team.members[0], slot="TUE_18_20", start_date=TUESDAY,
                           reason="x"))
    db.session.commit()
    res = as_assistant.post(f"/teams/{team.id}/delete")
    assert res.status_code == 302
    assert _reload(db, Team, team.id) is None
    assert db.session.execute(db.select(Student)).first() is None
    assert db.session.execute(db.select(Absence)).first() is None


def test_delete_requires_post(as_assistant, assistant):
    team = add_team(assistant)
    assert as_assistant.get(f"/teams/{team.id}/delete").status_code == 405


def test_navbar_has_teams_link(as_assistant):
    assert 'href="/teams/"' in as_assistant.get("/dashboard/").get_data(as_text=True)


# --- import -------------------------------------------------------------------------

LIST = """
Tuesday:

Popescu Adrian Mihai    Urs Robert Sebastian
Balc Dragos    - benrhouma aya
Ana Pop | Ion Ionescu

Thursday:
Giba Daniel\tPopescu David
"""


def test_parse_teams_accepts_the_pasted_format():
    assert parse_teams(LIST) == [
        ("TUE_18_20", ["Popescu Adrian Mihai", "Urs Robert Sebastian"]),
        ("TUE_18_20", ["Balc Dragos", "benrhouma aya"]),
        ("TUE_18_20", ["Ana Pop", "Ion Ionescu"]),
        ("THU_18_20", ["Giba Daniel", "Popescu David"]),
    ]


def test_parse_teams_needs_a_day_header():
    with pytest.raises(TeamError, match="Line 1"):
        parse_teams("Ana Pop | Ion Ionescu")


def test_import_is_idempotent(db, assistant):
    assert import_teams(assistant, LIST) == (4, 0)
    assert import_teams(assistant, LIST) == (0, 4)
    assert db.session.execute(db.select(db.func.count(Team.id))).scalar() == 4
    # Same team listed again in the other order is skipped too.
    assert import_teams(assistant, "Tuesday:\nIon Ionescu | Ana Pop") == (0, 1)


def test_import_is_all_or_nothing(db, assistant):
    # "Ana Pop" is already in the first team, so the second team is a conflict.
    with pytest.raises(TeamError, match="already in another team"):
        import_teams(assistant, "Tuesday:\nAna Pop | Ion Ionescu\nAna Pop | Dan Stan")
    assert db.session.execute(db.select(Team)).first() is None
