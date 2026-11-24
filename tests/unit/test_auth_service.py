"""AuthService business rules (FR-01, FR-02, FR-03)."""
from datetime import timedelta

import pytest

from app.models import Collection, User
from app.models.enums import AccountStatus
from app.services.auth_service import GENERIC_SIGN_IN_ERROR, SUSPENDED_ERROR, AuthService
from app.services.errors import AuthenticationError, ValidationError
from app.utils import utcnow

PASSWORD = "Passw0rd!"


def register(username="alice", email="alice@example.com", display_name="Alice", password=PASSWORD,
             confirmation=None):
    return AuthService.register(username, email, display_name, password,
                                password if confirmation is None else confirmation)


# --- FR-01 ------------------------------------------------------------------
def test_register_creates_active_user_with_favorites(db):
    user = register()
    assert user.id is not None
    assert user.role == "Registered" and user.status == "Active"
    assert user.password_hash != PASSWORD
    favorites = db.session.query(Collection).filter_by(user_id=user.id).all()
    assert [(c.name, c.is_default) for c in favorites] == [("Favorites", True)]


def test_register_trims_and_lowercases_email(db):
    user = register(username="  bob_1 ", email=" Bob@Example.COM ", display_name=" Bob ")
    assert user.username == "bob_1"
    assert user.email == "bob@example.com"
    assert user.display_name == "Bob"


def test_register_reports_every_invalid_field_at_once(db):
    with pytest.raises(ValidationError) as exc:
        register(username="a", email="nope", display_name="", password="short", confirmation="other")
    assert set(exc.value.errors) == {"username", "email", "display_name", "password", "password_confirmation"}
    assert db.session.query(User).count() == 0


@pytest.mark.parametrize("username,email,field", [
    ("ALICE", "new@example.com", "username"),
    ("newname", "ALICE@example.com", "email"),
])
def test_register_rejects_duplicates_ignoring_case(db, username, email, field):
    register()
    with pytest.raises(ValidationError) as exc:
        register(username=username, email=email)
    assert field in exc.value.errors
    assert db.session.query(User).count() == 1


# --- FR-02 ------------------------------------------------------------------
@pytest.mark.parametrize("identifier", ["alice", "ALICE", "alice@example.com", "Alice@Example.com"])
def test_sign_in_with_username_or_email(db, identifier):
    register()
    assert AuthService.authenticate(identifier, PASSWORD).username == "alice"


def test_unknown_user_and_wrong_password_get_same_message(db):
    register()
    with pytest.raises(AuthenticationError) as unknown:
        AuthService.authenticate("nobody", PASSWORD)
    with pytest.raises(AuthenticationError) as wrong:
        AuthService.authenticate("alice", "Wrong1234")
    assert unknown.value.message == wrong.value.message == GENERIC_SIGN_IN_ERROR


def test_empty_credentials_are_refused(db):
    with pytest.raises(AuthenticationError):
        AuthService.authenticate("", "")


def test_fifth_wrong_password_locks_for_15_minutes(db):
    user = register()
    for _ in range(4):
        with pytest.raises(AuthenticationError):
            AuthService.authenticate("alice", "Wrong1234")
    assert user.failed_login_attempts == 4 and user.lock_until is None

    with pytest.raises(AuthenticationError):
        AuthService.authenticate("alice", "Wrong1234")
    assert user.lock_until is not None
    remaining = user.lock_until - utcnow()
    assert timedelta(minutes=14) < remaining <= timedelta(minutes=15)

    # Even the correct password is refused while locked.
    with pytest.raises(AuthenticationError) as exc:
        AuthService.authenticate("alice", PASSWORD)
    assert "Try again in" in exc.value.message


def test_sign_in_works_again_after_lock_expires(db):
    user = register()
    user.lock_until = utcnow() - timedelta(seconds=1)
    db.session.commit()
    assert AuthService.authenticate("alice", PASSWORD) == user
    assert user.lock_until is None


def test_successful_sign_in_resets_failure_counter(db):
    user = register()
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            AuthService.authenticate("alice", "Wrong1234")
    AuthService.authenticate("alice", PASSWORD)
    assert user.failed_login_attempts == 0


def test_suspended_account_is_refused_with_clear_message(db):
    user = register()
    user.status = AccountStatus.SUSPENDED
    db.session.commit()
    with pytest.raises(AuthenticationError) as exc:
        AuthService.authenticate("alice", PASSWORD)
    assert exc.value.message == SUSPENDED_ERROR


def test_suspended_account_with_wrong_password_gets_generic_message(db):
    user = register()
    user.status = AccountStatus.SUSPENDED
    db.session.commit()
    with pytest.raises(AuthenticationError) as exc:
        AuthService.authenticate("alice", "Wrong1234")
    assert exc.value.message == GENERIC_SIGN_IN_ERROR


# --- FR-03 ------------------------------------------------------------------
def test_update_profile(db):
    user = register()
    AuthService.update_profile(user, "  Alice A. ", "  I write prompts. ")
    assert user.display_name == "Alice A."
    assert user.bio == "I write prompts."
    AuthService.update_profile(user, "Alice", "")
    assert user.bio is None


def test_update_profile_rejects_invalid_values(db):
    user = register()
    with pytest.raises(ValidationError) as exc:
        AuthService.update_profile(user, "", "x" * 301)
    assert set(exc.value.errors) == {"display_name", "bio"}
    db.session.refresh(user)
    assert user.display_name == "Alice"


def test_change_password(db):
    user = register()
    AuthService.change_password(user, PASSWORD, "NewPass99", "NewPass99")
    assert user.check_password("NewPass99")
    assert not user.check_password(PASSWORD)


def test_change_password_wrong_current_keeps_old_password(db):
    user = register()
    with pytest.raises(ValidationError) as exc:
        AuthService.change_password(user, "Wrong1234", "NewPass99", "NewPass99")
    assert "current_password" in exc.value.errors
    assert user.check_password(PASSWORD)


def test_change_password_validates_new_password(db):
    user = register()
    with pytest.raises(ValidationError) as exc:
        AuthService.change_password(user, PASSWORD, "weak", "different")
    assert set(exc.value.errors) == {"new_password", "new_password_confirmation"}
    assert user.check_password(PASSWORD)


# --- Review fixes -------------------------------------------------------------
def test_register_race_reports_the_field_that_collided(db, monkeypatch):
    register()
    # Simulate another request winning the race: the pre-checks see nothing, the commit fails.
    calls = {"n": 0}

    def taken_only_after_rollback(email):
        calls["n"] += 1
        return calls["n"] > 1

    monkeypatch.setattr(AuthService, "_email_taken", staticmethod(taken_only_after_rollback))
    with pytest.raises(ValidationError) as exc:
        register(username="different", email="alice@example.com")
    assert set(exc.value.errors) == {"email"}
    assert db.session.query(User).count() == 1
    assert db.session.query(Collection).count() == 1  # nothing half-created


def test_register_with_administrator_role(db):
    user = AuthService.register("admin", "admin@example.com", "Admin", PASSWORD, PASSWORD, role="Administrator")
    assert user.is_admin


def test_oversized_credentials_get_generic_error_without_counting(db):
    user = register()
    with pytest.raises(AuthenticationError) as exc:
        AuthService.authenticate("alice", "x" * 500)
    assert exc.value.message == GENERIC_SIGN_IN_ERROR
    assert user.failed_login_attempts == 0
