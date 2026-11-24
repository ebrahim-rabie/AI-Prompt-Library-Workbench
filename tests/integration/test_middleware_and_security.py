"""AuthMiddleware and security checks (FR-02 timeout, NFR-02, NFR-04)."""
import time

from app import create_app
from app.extensions import db as _db
from app.middleware.auth import SESSION_LAST_SEEN_KEY
from app.models import User
from tests.conftest import sign_in


# --- NFR-02b: 401 when signed out, 403 when not allowed ----------------------
def test_protected_route_gives_401_when_signed_out(client):
    response = client.get("/_probe/member")
    assert response.status_code == 401
    assert "/login?next=" in response.get_data(as_text=True)


def test_admin_route_gives_401_then_403_for_non_admin(client, make_user):
    assert client.get("/_probe/admin").status_code == 401
    make_user("alice")
    sign_in(client, "alice")
    assert client.get("/_probe/admin").status_code == 403


def test_admin_route_allows_administrator(client, db, make_user):
    admin = make_user("admin")
    admin.role = "Administrator"
    db.session.commit()
    sign_in(client, "admin")
    assert client.get("/_probe/admin").status_code == 200


def test_owner_check(client, make_user):
    alice = make_user("alice")
    bob = make_user("bob")
    sign_in(client, "alice")
    assert client.get(f"/_probe/owned-by/{alice.id}").status_code == 200
    assert client.get(f"/_probe/owned-by/{bob.id}").status_code == 403


# --- FR-02: 60 minutes of inactivity ends the session ------------------------
def test_session_expires_after_60_minutes_of_inactivity(client, make_user):
    make_user("alice")
    sign_in(client, "alice")
    assert client.get("/_probe/member").status_code == 200

    with client.session_transaction() as session:
        session[SESSION_LAST_SEEN_KEY] = time.time() - 61 * 60
    assert client.get("/_probe/member").status_code == 401


def test_activity_keeps_session_alive(client, make_user):
    make_user("alice")
    sign_in(client, "alice")
    with client.session_transaction() as session:
        session[SESSION_LAST_SEEN_KEY] = time.time() - 59 * 60
    assert client.get("/_probe/member").status_code == 200
    with client.session_transaction() as session:
        assert time.time() - session[SESSION_LAST_SEEN_KEY] < 5


def test_user_suspended_while_signed_in_loses_session(client, db, make_user):
    user = make_user("alice")
    sign_in(client, "alice")
    user.status = "Suspended"
    db.session.commit()
    assert client.get("/_probe/member").status_code == 401


# --- NFR-02a / NFR-02c -------------------------------------------------------
def test_passwords_are_never_stored_readable(db, make_user):
    for i in range(5):
        make_user(f"user{i}", password=f"Secret{i}pass")
    for i, user in enumerate(db.session.query(User).order_by(User.id)):
        assert f"Secret{i}pass" not in user.password_hash
        assert user.password_hash.startswith(("scrypt:", "pbkdf2:"))


def test_user_text_is_escaped(client, make_user):
    make_user("alice", display_name="<script>alert(1)</script>")
    sign_in(client, "alice")
    page = client.get("/profile").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_security_headers_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


# --- NFR-04: errors never show a stack trace ---------------------------------
def test_unknown_page_shows_friendly_404(client):
    response = client.get("/does-not-exist")
    page = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Page not found" in page and "Traceback" not in page


def test_invalid_requests_never_crash(client, make_user):
    make_user("alice")
    bad_inputs = [
        ("/register", {}),
        ("/register", {"username": "x" * 5000, "email": "@", "password": "\x00"}),
        ("/login", {}),
        ("/login", {"identifier": "' OR 1=1 --", "password": "x"}),
    ]
    for url, data in bad_inputs:
        assert client.post(url, data=data).status_code < 500


# --- CSRF protection (enabled outside the test config) ------------------------
def test_forms_without_csrf_token_are_rejected(monkeypatch):
    from app.config import TestingConfig

    monkeypatch.setattr(TestingConfig, "WTF_CSRF_ENABLED", True)
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        try:
            response = app.test_client().post("/login", data={"identifier": "a", "password": "b"})
            assert response.status_code == 400
            assert "The form expired" in response.get_data(as_text=True)
        finally:
            _db.session.remove()
            _db.drop_all()


# --- Review fixes -------------------------------------------------------------
def test_password_change_signs_out_other_sessions(app, make_user):
    make_user("alice")
    laptop, phone = app.test_client(), app.test_client()
    sign_in(laptop, "alice")
    sign_in(phone, "alice")

    response = laptop.post("/profile/password", data={
        "current_password": "Passw0rd!", "new_password": "NewPass99", "new_password_confirmation": "NewPass99",
    })
    assert response.status_code == 302
    assert laptop.get("/_probe/member").status_code == 200   # the session that changed it stays in
    assert phone.get("/_probe/member").status_code == 401    # the other session is signed out


def test_expired_session_explains_why(client, make_user):
    make_user("alice")
    sign_in(client, "alice")
    with client.session_transaction() as session:
        session[SESSION_LAST_SEEN_KEY] = time.time() - 61 * 60
    page = client.get("/", follow_redirects=True).get_data(as_text=True)
    assert "Your session ended after 60 minutes without activity." in page


def test_next_with_control_characters_is_ignored(client, make_user):
    make_user("alice")
    for sneaky in ("/\t/evil.example", "/\n/evil.example", "/ /evil.example"):
        response = sign_in(client, "alice", next_url=sneaky)
        assert response.headers["Location"] == "/"
        client.post("/logout")


def test_401_page_offers_next_only_for_get(client):
    assert "next=" in client.get("/_probe/member").get_data(as_text=True)
    assert "next=" not in client.post("/profile").get_data(as_text=True)


def test_uncommon_http_errors_keep_their_status_and_headers(client):
    response = client.get("/logout")
    assert response.status_code == 405
    assert "POST" in response.headers["Allow"]

    response = client.post("/login", data={"identifier": "a", "password": "x" * (1024 * 1024 + 10)})
    assert response.status_code == 413
    assert "Request too large" in response.get_data(as_text=True)


def test_content_security_policy_header(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp


def test_https_redirect_keeps_method_and_sets_hsts(monkeypatch):
    from app.config import TestingConfig

    monkeypatch.setattr(TestingConfig, "FORCE_HTTPS", True)
    app = create_app("testing")
    client = app.test_client()
    response = client.post("/login", data={"identifier": "a", "password": "b"})
    assert response.status_code == 308
    assert response.headers["Location"].startswith("https://")
    secure = client.get("/", base_url="https://localhost")
    assert secure.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_production_refuses_weak_or_placeholder_secret_key(monkeypatch):
    import pytest
    from app.config import ProductionConfig

    for weak in (None, "", "change-me", "dev-only-insecure-key", "short-but-random-123"):
        monkeypatch.setattr(ProductionConfig, "SECRET_KEY", weak)
        with pytest.raises(RuntimeError):
            create_app("production")

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a" * 16 + "7f3c9e2b1d4a6f8e0c5b9a7d3e1f2c4b")
    assert create_app("production").config["SESSION_COOKIE_SECURE"] is True


def test_development_without_secret_key_uses_random_key(monkeypatch):
    from app.config import DevelopmentConfig

    monkeypatch.setattr(DevelopmentConfig, "SECRET_KEY", None)
    first, second = create_app("development"), create_app("development")
    assert len(first.secret_key) == 64
    assert first.secret_key != second.secret_key


def test_not_owner(app, make_user):
    from flask import g

    from app.middleware.auth import AuthMiddleware

    alice, bob = make_user("alice"), make_user("bob")
    with app.test_request_context():
        g.user = None
        assert not AuthMiddleware.not_owner(alice.id)   # signed out: not allowed either
        g.user = alice
        assert not AuthMiddleware.not_owner(alice.id)   # own prompt: cannot rate/review/report/fork
        assert AuthMiddleware.not_owner(bob.id)
