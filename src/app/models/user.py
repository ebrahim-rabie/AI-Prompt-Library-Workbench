"""User entity (table: users) - accounts and sign-in state. Guests are not stored.

Matches the User entity of the class diagram (Design Figure 3). Password hashing,
password checks and the lock check belong to AuthService (Figure 3); the entity
only stores the data and offers the two model calls used in Figure 4.
"""
from sqlalchemy import CheckConstraint, Index, func, or_

from ..extensions import db
from ..utils import utcnow
from .enums import AccountStatus, Role, check_in


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.String(300), nullable=True)
    role = db.Column(db.String(20), nullable=False, default=Role.REGISTERED, server_default=Role.REGISTERED)
    status = db.Column(db.String(20), nullable=False, default=AccountStatus.ACTIVE,
                       server_default=AccountStatus.ACTIVE)
    registered_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    lock_until = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        # Unique without regard to letter case (FR-01).
        Index("uq_users_username_lower", func.lower(username), unique=True),
        Index("uq_users_email_lower", func.lower(email), unique=True),
        CheckConstraint(check_in("role", Role.ALL), name="role_valid"),
        CheckConstraint(check_in("status", AccountStatus.ALL), name="status_valid"),
        CheckConstraint("failed_login_attempts >= 0", name="failed_attempts_non_negative"),
    )

    prompts = db.relationship("Prompt", back_populates="owner", lazy="dynamic")
    collections = db.relationship("Collection", back_populates="user", lazy="dynamic",
                                  cascade="all, delete-orphan")

    # --- Figure 4 model calls -------------------------------------------------
    @classmethod
    def find_by_username_or_email(cls, identifier):
        """Return the user whose username or email matches (any letter case), or None."""
        value = (identifier or "").strip().lower()
        if not value:
            return None
        return cls.query.filter(or_(func.lower(cls.username) == value, func.lower(cls.email) == value)).first()

    def reset_failed_attempts(self):
        """Clear the failure counter and any lock after a correct password (Figure 4)."""
        self.failed_login_attempts = 0
        self.lock_until = None

    # --- read-only helpers ----------------------------------------------------
    @property
    def is_admin(self):
        return self.role == Role.ADMINISTRATOR

    @property
    def is_suspended(self):
        return self.status == AccountStatus.SUSPENDED

    def __repr__(self):
        return f"<User {self.id} {self.username!r}>"
