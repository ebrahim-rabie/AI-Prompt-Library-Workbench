"""AuthService - accounts, sign in and profile (FR-01, FR-02, FR-03; UC-01, UC-02, UC-03).

Method names follow the AuthService class of Design Figure 3:
registerUser(), authenticate(), recordFailedAttempt(), isLocked(),
hashPassword(), verifyPassword(), changePassword(), updateProfile().
"""
import math

from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import User
from ..models import validators
from ..models.enums import AccountStatus, Role
from ..utils import utcnow
from .collection_service import CollectionService
from .errors import AuthenticationError, ValidationError

GENERIC_SIGN_IN_ERROR = "The username, email or password is not correct."
SUSPENDED_ERROR = "This account is suspended. Contact an administrator if you think this is a mistake."

# Compared against when the user does not exist, so a wrong username takes as long as a wrong password.
_DUMMY_HASH = generate_password_hash("timing-equaliser-not-a-real-password")


def _clean(value):
    return (value or "").strip()


class AuthService:
    # --- passwords (NFR-02a: only a salted hash is stored) ----------------------
    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)

    @staticmethod
    def verify_password(user, password):
        return check_password_hash(user.password_hash, password or "")

    # --- FR-01 Register (UC-01) --------------------------------------------------
    @staticmethod
    def register_user(username, email, display_name, password, password_confirmation, role=Role.REGISTERED):
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
                    password_hash=AuthService.hash_password(password),
                    role=role, status=AccountStatus.ACTIVE)
        CollectionService.ensure_favorites(user)  # Figure 3: AuthService -> CollectionService
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

    # --- FR-02 Sign in (UC-02, Design Figure 4) ---------------------------------
    @staticmethod
    def authenticate(identifier, password):
        """Return the user when the credentials are valid, else raise AuthenticationError.

        Steps follow Figure 4: findByUsernameOrEmail -> lock -> password -> status.
        """
        identifier = _clean(identifier)
        password = password or ""
        if not identifier or not password:
            raise AuthenticationError("Enter your username or email and your password.")
        if len(identifier) > validators.EMAIL_MAX or len(password) > validators.PASSWORD_MAX:
            # No real account can match; refuse before doing any expensive hashing.
            raise AuthenticationError(GENERIC_SIGN_IN_ERROR)

        user = User.find_by_username_or_email(identifier)
        if user is None:  # [user not found]
            check_password_hash(_DUMMY_HASH, password)
            raise AuthenticationError(GENERIC_SIGN_IN_ERROR)

        now = utcnow()
        if AuthService.is_locked(user, now):  # [account locked (lockUntil is in the future)]
            minutes = max(1, math.ceil((user.lock_until - now).total_seconds() / 60))
            raise AuthenticationError(
                f"Too many failed sign-in attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
            )

        if not AuthService.verify_password(user, password):  # [wrong password]
            AuthService.record_failed_attempt(user, now)
            raise AuthenticationError(GENERIC_SIGN_IN_ERROR)

        user.reset_failed_attempts()
        db.session.commit()

        if user.is_suspended:  # [account suspended]
            raise AuthenticationError(SUSPENDED_ERROR)
        return user  # [valid and active] -> AuthController asks AuthMiddleware.create_session()

    @staticmethod
    def is_locked(user, now=None):
        now = now or utcnow()
        return user.lock_until is not None and user.lock_until > now

    @staticmethod
    def record_failed_attempt(user, now=None):
        """Count a wrong password; the 5th one in a row locks the account for 15 minutes."""
        now = now or utcnow()
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

    # --- FR-03 Manage profile (UC-03) --------------------------------------------
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
        if not AuthService.verify_password(user, current_password):
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

        user.password_hash = AuthService.hash_password(new_password)
        db.session.commit()
        return user
