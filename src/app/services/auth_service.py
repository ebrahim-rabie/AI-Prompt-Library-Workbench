"""AuthService - accounts, sign in and profile (FR-01, FR-02, FR-03; UC-01, UC-02, UC-03)."""
import math

from flask import current_app
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import FAVORITES_NAME, Collection, User
from ..models.enums import AccountStatus, Role
from ..models import validators
from ..utils import utcnow
from .errors import AuthenticationError, ValidationError

GENERIC_SIGN_IN_ERROR = "The username, email or password is not correct."
SUSPENDED_ERROR = "This account is suspended. Contact an administrator if you think this is a mistake."

# Compared against when the user does not exist, so a wrong username takes as long as a wrong password.
_DUMMY_HASH = generate_password_hash("timing-equaliser-not-a-real-password")


def _clean(value):
    return (value or "").strip()


class AuthService:
    # --- FR-01 Register ------------------------------------------------------
    @staticmethod
    def register(username, email, display_name, password, password_confirmation, role=Role.REGISTERED):
        """Create an active account and its Favorites collection in one transaction.

        `role` is Registered for sign-ups; only the seed script passes Administrator.
        Raises ValidationError with every invalid field.
        """
        username = _clean(username)
        email = _clean(email).lower()
        display_name = _clean(display_name)

        errors = {}
        for field, message in (
            ("username", validators.validate_username(username)),
            ("email", validators.validate_email(email)),
            ("display_name", validators.validate_display_name(display_name)),
            ("password", validators.validate_password(password)),
            ("password_confirmation", validators.validate_password_confirmation(password, password_confirmation)),
        ):
            if message:
                errors[field] = message

        if "username" not in errors and AuthService._username_taken(username):
            errors["username"] = "This username is already taken."
        if "email" not in errors and AuthService._email_taken(email):
            errors["email"] = "An account with this email already exists."
        if errors:
            raise ValidationError(errors)

        user = User(username=username, email=email, display_name=display_name,
                    role=role, status=AccountStatus.ACTIVE)
        user.set_password(password)
        user.collections.append(Collection(name=FAVORITES_NAME, is_default=True))
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Another request registered the same username or email between the check and the commit.
            db.session.rollback()
            errors = {}
            if AuthService._username_taken(username):
                errors["username"] = "This username is already taken."
            if AuthService._email_taken(email):
                errors["email"] = "An account with this email already exists."
            if not errors:
                raise  # not a duplicate: let the error page handle it
            raise ValidationError(errors)
        return user

    @staticmethod
    def _username_taken(username):
        return db.session.query(User.id).filter(func.lower(User.username) == username.lower()).first() is not None

    @staticmethod
    def _email_taken(email):
        return db.session.query(User.id).filter(func.lower(User.email) == email.lower()).first() is not None

    # --- FR-02 Sign in -------------------------------------------------------
    @staticmethod
    def authenticate(identifier, password):
        """Return the user when the credentials are valid, else raise AuthenticationError.

        Order follows Design Figure 4: find user -> lock -> password -> status.
        """
        identifier = _clean(identifier)
        password = password or ""
        if not identifier or not password:
            raise AuthenticationError("Enter your username or email and your password.")
        if len(identifier) > validators.EMAIL_MAX or len(password) > validators.PASSWORD_MAX:
            # No real account can match; refuse before doing any expensive hashing.
            raise AuthenticationError(GENERIC_SIGN_IN_ERROR)

        user = (
            db.session.query(User)
            .filter(or_(func.lower(User.username) == identifier.lower(),
                        func.lower(User.email) == identifier.lower()))
            .first()
        )
        if user is None:
            check_password_hash(_DUMMY_HASH, password)
            raise AuthenticationError(GENERIC_SIGN_IN_ERROR)

        now = utcnow()
        if user.is_locked(now):
            minutes = max(1, math.ceil((user.lock_until - now).total_seconds() / 60))
            raise AuthenticationError(
                f"Too many failed sign-in attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
            )

        if not user.check_password(password):
            AuthService._record_failed_attempt(user, now)
            raise AuthenticationError(GENERIC_SIGN_IN_ERROR)

        user.failed_login_attempts = 0
        user.lock_until = None
        db.session.commit()

        if user.is_suspended:
            raise AuthenticationError(SUSPENDED_ERROR)
        return user

    @staticmethod
    def _record_failed_attempt(user, now):
        max_attempts = current_app.config["LOGIN_MAX_FAILED_ATTEMPTS"]
        # Increment in SQL (SET failed_login_attempts = failed_login_attempts + 1) so parallel
        # wrong guesses cannot overwrite each other's count and dodge the lockout.
        user.failed_login_attempts = User.failed_login_attempts + 1
        db.session.flush()
        db.session.refresh(user, ["failed_login_attempts"])
        if user.failed_login_attempts >= max_attempts:
            user.lock_until = now + current_app.config["LOGIN_LOCK_DURATION"]
            user.failed_login_attempts = 0  # a fresh count starts after the lock ends
        db.session.commit()

    # --- FR-03 Manage profile ------------------------------------------------
    @staticmethod
    def update_profile(user, display_name, bio):
        display_name = _clean(display_name)
        bio = _clean(bio)
        errors = {}
        for field, message in (
            ("display_name", validators.validate_display_name(display_name)),
            ("bio", validators.validate_bio(bio)),
        ):
            if message:
                errors[field] = message
        if errors:
            raise ValidationError(errors)

        user.display_name = display_name
        user.bio = bio or None
        db.session.commit()
        return user

    @staticmethod
    def change_password(user, current_password, new_password, new_password_confirmation):
        if not user.check_password(current_password or ""):
            raise ValidationError({"current_password": "The current password is not correct."})

        errors = {}
        message = validators.validate_password(new_password)
        if message:
            errors["new_password"] = message
        message = validators.validate_password_confirmation(new_password, new_password_confirmation)
        if message:
            errors["new_password_confirmation"] = message
        if errors:
            raise ValidationError(errors)

        user.set_password(new_password)
        db.session.commit()
        return user
