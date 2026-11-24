"""Shared pytest fixtures: a fresh in-memory database for every test."""
import pytest
from flask import Blueprint, g

from app import create_app
from app.extensions import db as _db
from app.middleware.auth import admin_required, login_required, require_owner
from app.services.auth_service import AuthService

DEFAULT_PASSWORD = "Passw0rd!"


def _register_probe_routes(app):
    """Tiny routes used only by tests to exercise the middleware decorators."""
    probe = Blueprint("probe", __name__, url_prefix="/_probe")

    @probe.route("/member")
    @login_required
    def member():
        return f"member {g.user.username}"

    @probe.route("/admin")
    @admin_required
    def admin():
        return "admin ok"

    @probe.route("/owned-by/<int:owner_id>")
    @login_required
    def owned(owner_id):
        require_owner(owner_id)
        return "owner ok"

    app.register_blueprint(probe)


@pytest.fixture
def app():
    app = create_app("testing")
    _register_probe_routes(app)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def make_user(app):
    counter = {"n": 0}

    def _make_user(username=None, email=None, display_name=None, password=DEFAULT_PASSWORD):
        counter["n"] += 1
        username = username or f"user{counter['n']}"
        return AuthService.register(
            username=username,
            email=email or f"{username}@example.com",
            display_name=display_name or username.title(),
            password=password,
            password_confirmation=password,
        )

    return _make_user


def sign_in(client, identifier, password=DEFAULT_PASSWORD, next_url=None):
    data = {"identifier": identifier, "password": password}
    if next_url is not None:
        data["next"] = next_url
    return client.post("/login", data=data)
