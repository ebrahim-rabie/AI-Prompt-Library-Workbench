"""User entity (table: users) - accounts and sign-in state. Guests are not stored."""
from sqlalchemy import CheckConstraint, Index, func
from werkzeug.security import check_password_hash, generate_password_hash

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

    # --- password (NFR-02a: only a salted hash is stored) -------------------
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # --- state helpers ------------------------------------------------------
    @property
    def is_admin(self):
        return self.role == Role.ADMINISTRATOR

    @property
    def is_suspended(self):
        return self.status == AccountStatus.SUSPENDED

    def is_locked(self, now=None):
        now = now or utcnow()
        return self.lock_until is not None and self.lock_until > now

    def __repr__(self):
        return f"<User {self.id} {self.username!r}>"
