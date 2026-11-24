"""Register, sign in and sign out through HTTP (FR-01, FR-02; UC-01, UC-02)."""
from app.models import User
from tests.conftest import DEFAULT_PASSWORD, sign_in


def register_form(**overrides):
    data = {
        "username": "alice",
        "email": "alice@example.com",
        "display_name": "Alice",
        "password": DEFAULT_PASSWORD,
        "password_confirmation": DEFAULT_PASSWORD,
    }
    data.update(overrides)
    return data


def test_pages_render(client):
    for url in ("/", "/register", "/login"):
        assert client.get(url).status_code == 200


def test_register_then_redirect_to_sign_in(client, db):
    response = client.post("/register", data=register_form())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert db.session.query(User).filter_by(username="alice").one()


def test_register_duplicate_email_keeps_other_values(client, make_user):
    make_user("alice", "alice@example.com")
    response = client.post("/register", data=register_form(username="alice2", display_name="Second Alice"))
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "An account with this email already exists." in page
    assert 'value="alice2"' in page and 'value="Second Alice"' in page
    assert DEFAULT_PASSWORD not in page  # passwords are never sent back


def test_register_weak_password_and_mismatch(client, db):
    response = client.post("/register", data=register_form(password="weakpass", password_confirmation="other"))
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Include at least one letter and one digit." in page
    assert "The passwords do not match." in page
    assert db.session.query(User).count() == 0


def test_sign_in_and_out(client, make_user):
    make_user("alice")
    response = sign_in(client, "alice")
    assert response.status_code == 302
    page = client.get("/").get_data(as_text=True)
    assert "Signed in as" in page and "Sign out" in page

    response = client.post("/logout")
    assert response.status_code == 302
    assert client.get("/_probe/member").status_code == 401


def test_wrong_password_shows_generic_message(client, make_user):
    make_user("alice")
    response = sign_in(client, "alice", "Wrong1234")
    assert response.status_code == 401
    assert "The username, email or password is not correct." in response.get_data(as_text=True)


def test_lockout_after_five_failures(client, make_user):
    make_user("alice")
    for _ in range(5):
        sign_in(client, "alice", "Wrong1234")
    response = sign_in(client, "alice")
    assert response.status_code == 401
    assert "Too many failed sign-in attempts" in response.get_data(as_text=True)


def test_suspended_user_cannot_sign_in(client, db, make_user):
    user = make_user("alice")
    user.status = "Suspended"
    db.session.commit()
    response = sign_in(client, "alice")
    assert response.status_code == 401
    assert "This account is suspended." in response.get_data(as_text=True)


def test_sign_in_redirects_to_safe_next_only(client, make_user):
    make_user("alice")
    response = sign_in(client, "alice", next_url="/profile")
    assert response.headers["Location"].endswith("/profile")

    client.post("/logout")
    for evil in ("https://evil.example/", "//evil.example/", "/\\evil.example"):
        response = sign_in(client, "alice", next_url=evil)
        assert "evil" not in response.headers["Location"]
        client.post("/logout")


def test_signed_in_user_is_sent_away_from_register_and_login(client, make_user):
    make_user("alice")
    sign_in(client, "alice")
    assert client.get("/register").status_code == 302
    assert client.get("/login").status_code == 302


def test_logout_requires_post(client):
    assert client.get("/logout").status_code == 405


def test_faq_page(client):
    response = client.get("/faq")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Frequently asked questions" in page and "How do versions work?" in page
