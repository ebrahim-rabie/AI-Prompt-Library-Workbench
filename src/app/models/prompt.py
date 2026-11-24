"""Prompt, PromptVersion and PromptVariable entities.

Tables: prompts, prompt_versions, prompt_variables (Design 4.4.3).
The authoring rules (variable sync, publish checks, versioning) live in the
services that use these models (PromptService / VersionService).
"""
from sqlalchemy import CheckConstraint, UniqueConstraint

from ..extensions import db
from ..utils import utcnow
from .enums import PromptStatus, TargetModel, VarType, check_in
from .tag import prompt_tags


class Prompt(db.Model):
    __tablename__ = "prompts"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    original_prompt_id = db.Column(db.Integer, db.ForeignKey("prompts.id"), nullable=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    target_model = db.Column(db.String(20), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default=PromptStatus.DRAFT,
                       server_default=PromptStatus.DRAFT, index=True)
    average_rating = db.Column(db.Numeric(2, 1, asdecimal=False), nullable=False, default=0,
                               server_default="0", index=True)
    fork_count = db.Column(db.Integer, nullable=False, default=0, server_default="0", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    __table_args__ = (
        CheckConstraint(check_in("status", PromptStatus.ALL), name="status_valid"),
        CheckConstraint(f"target_model IS NULL OR {check_in('target_model', TargetModel.ALL)}",
                        name="target_model_valid"),
        CheckConstraint("average_rating >= 0 AND average_rating <= 5", name="average_rating_range"),
        CheckConstraint("fork_count >= 0", name="fork_count_non_negative"),
    )

    owner = db.relationship("User", back_populates="prompts")
    original = db.relationship("Prompt", remote_side=[id], backref=db.backref("forks", lazy="dynamic"))
    versions = db.relationship("PromptVersion", back_populates="prompt", order_by="PromptVersion.version_number",
                               cascade="all, delete-orphan")
    tags = db.relationship("Tag", secondary=prompt_tags, back_populates="prompts")

    @property
    def latest_version(self):
        return self.versions[-1] if self.versions else None

    def __repr__(self):
        return f"<Prompt {self.id} {self.title!r} {self.status}>"


class PromptVersion(db.Model):
    __tablename__ = "prompt_versions"

    id = db.Column(db.Integer, primary_key=True)
    prompt_id = db.Column(db.Integer, db.ForeignKey("prompts.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    template_body = db.Column(db.Text, nullable=False, default="")
    change_note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("prompt_id", "version_number", name="uq_prompt_versions_prompt_number"),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
    )

    prompt = db.relationship("Prompt", back_populates="versions")
    variables = db.relationship("PromptVariable", back_populates="version", order_by="PromptVariable.id",
                                cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PromptVersion prompt={self.prompt_id} v{self.version_number}>"


class PromptVariable(db.Model):
    __tablename__ = "prompt_variables"

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey("prompt_versions.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    data_type = db.Column(db.String(20), nullable=False, default=VarType.TEXT, server_default=VarType.TEXT)
    default_value = db.Column(db.String(500), nullable=True)
    is_required = db.Column(db.Boolean, nullable=False, default=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("version_id", "name", name="uq_prompt_variables_version_name"),
        CheckConstraint(check_in("data_type", VarType.ALL), name="data_type_valid"),
    )

    version = db.relationship("PromptVersion", back_populates="variables")

    def __repr__(self):
        return f"<PromptVariable {self.name!r} {self.data_type}>"
