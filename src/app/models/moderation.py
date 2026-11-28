"""Report and ModerationAction entities (tables: reports, moderation_actions)."""
from sqlalchemy import CheckConstraint, UniqueConstraint

from ..extensions import db
from ..utils import utcnow
from .enums import ActionType, ReportReason, ReportStatus, check_in


class ModerationAction(db.Model):
    """Audit record of an administrator decision (FR-19)."""

    __tablename__ = "moderation_actions"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action_type = db.Column(db.String(20), nullable=False)
    note = db.Column(db.String(500), nullable=True)  # required for Suspend, checked by the service
    executed_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint(check_in("action_type", ActionType.ALL), name="action_type_valid"),
    )

    admin = db.relationship("User")
    reports = db.relationship("Report", back_populates="moderation_action")


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_prompt_id = db.Column(db.Integer, db.ForeignKey("prompts.id"), nullable=True)
    target_review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=True)
    moderation_action_id = db.Column(db.Integer, db.ForeignKey("moderation_actions.id"), nullable=True)
    reason = db.Column(db.String(30), nullable=False)
    details = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=ReportStatus.PENDING,
                       server_default=ReportStatus.PENDING, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    __table_args__ = (
        # A report targets exactly one prompt or one review, never both ({xor}).
        CheckConstraint(
            "(target_prompt_id IS NOT NULL AND target_review_id IS NULL) OR "
            "(target_prompt_id IS NULL AND target_review_id IS NOT NULL)",
            name="exactly_one_target",
        ),
        CheckConstraint(check_in("reason", ReportReason.ALL), name="reason_valid"),
        CheckConstraint(check_in("status", ReportStatus.ALL), name="status_valid"),
        # A user reports the same item only once (FR-18).
        UniqueConstraint("reporter_id", "target_prompt_id", name="uq_reports_reporter_prompt"),
        UniqueConstraint("reporter_id", "target_review_id", name="uq_reports_reporter_review"),
    )

    reporter = db.relationship("User")
    target_prompt = db.relationship("Prompt")
    target_review = db.relationship("Review")
    moderation_action = db.relationship("ModerationAction", back_populates="reports")
