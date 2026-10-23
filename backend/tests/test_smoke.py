from app.models import User


def test_index_renders_with_bootstrap_and_slots(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "bootstrap@5.3.3" in html
    assert "Tuesday 18–20" in html
    assert "Thursday 18–20" in html


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_static_css_served(client):
    assert client.get("/static/css/app.css").status_code == 200


def test_init_db_creates_admin_once(app, db):
    runner = app.test_cli_runner()
    args = ["init-db", "--email", "prof@upt.ro", "--name", "Prof", "--password", "pw12345"]

    result = runner.invoke(args=args)
    assert result.exit_code == 0, result.output
    assert "Created admin" in result.output

    result = runner.invoke(args=args)
    assert "already exists" in result.output

    admins = db.session.execute(db.select(User).filter_by(email="prof@upt.ro")).scalars().all()
    assert len(admins) == 1
    assert admins[0].is_admin
    assert admins[0].check_password("pw12345")
