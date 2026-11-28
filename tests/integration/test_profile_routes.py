"""Profile page through HTTP (FR-03; UC-03)."""
from tests.conftest import DEFAULT_PASSWORD, sign_in


def test_profile_requires_sign_in(client):
    response = client.get("/profile")
    assert response.status_code == 401
    assert "Sign in required" in response.get_data(as_text=True)


def test_profile_shows_read_only_username_and_email(client, make_user):
    make_user("alice", "alice@example.com")
    sign_in(client, "alice")
    page = client.get("/profile").get_data(as_text=True)
    assert "alice@example.com" in page
    assert "Username and email cannot be changed." in page


def test_update_profile(client, make_user):
    user = make_user("alice")
    sign_in(client, "alice")
    response = client.post("/profile", data={"display_name": "Alice A.", "bio": "Prompt writer"})
    assert response.status_code == 302
    assert user.display_name == "Alice A." and user.bio == "Prompt writer"


def test_update_profile_ignores_username_and_email_fields(client, make_user):
    user = make_user("alice", "alice@example.com")
    sign_in(client, "alice")
    client.post("/profile", data={"display_name": "Alice", "bio": "", "username": "hacker",
                                  "email": "hacker@example.com"})
    assert user.username == "alice" and user.email == "alice@example.com"


def test_update_profile_invalid_bio(client, make_user):
    make_user("alice")
    sign_in(client, "alice")
    response = client.post("/profile", data={"display_name": "Alice", "bio": "x" * 301})
    assert response.status_code == 400
    assert "Keep the bio to 300 characters or fewer." in response.get_data(as_text=True)


def test_change_password_then_sign_in_with_new_one(client, make_user):
    make_user("alice")
    sign_in(client, "alice")
    response = client.post("/profile/password", data={
        "current_password": DEFAULT_PASSWORD,
        "new_password": "NewPass99",
        "new_password_confirmation": "NewPass99",
    })
    assert response.status_code == 302
    client.post("/logout")
    assert sign_in(client, "alice", "NewPass99").status_code == 302


def test_change_password_wrong_current(client, make_user):
    make_user("alice")
    sign_in(client, "alice")
    response = client.post("/profile/password", data={
        "current_password": "Wrong1234",
        "new_password": "NewPass99",
        "new_password_confirmation": "NewPass99",
    })
    assert response.status_code == 400
    assert "The current password is not correct." in response.get_data(as_text=True)
    client.post("/logout")
    assert sign_in(client, "alice", DEFAULT_PASSWORD).status_code == 302
