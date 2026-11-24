"""Rating and Review entities (tables: ratings, reviews)."""
from sqlalchemy import CheckConstraint, UniqueConstraint

from ..extensions import db
from ..utils import utcnow
from .enums import ReviewStatus, check_in


class Rating(db.Model):
    __tablename__ = "ratings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    prompt_id = db.Column(db.Integer, db.ForeignKey("prompts.id"), nullable=False, index=True)
    value = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "prompt_id", name="uq_ratings_user_prompt"),
        CheckConstraint("value >= 1 AND value <= 5", name="value_range"),
    )

    user = db.relationship("User")
    prompt = db.relationship("Prompt", backref=db.backref("ratings", lazy="dynamic"))


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    prompt_id = db.Column(db.Integer, db.ForeignKey("prompts.id"), nullable=False, index=True)
    comment = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ReviewStatus.VISIBLE,
                       server_default=ReviewStatus.VISIBLE)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "prompt_id", name="uq_reviews_user_prompt"),
        CheckConstraint(check_in("status", ReviewStatus.ALL), name="status_valid"),
    )

    user = db.relationship("User")
    prompt = db.relationship("Prompt", backref=db.backref("reviews", lazy="dynamic"))
