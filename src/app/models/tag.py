"""Tag entity (table: tags) and the prompt_tags link table."""
from sqlalchemy import CheckConstraint, Index, func

from ..extensions import db
from .enums import TagCategory, check_in

prompt_tags = db.Table(
    "prompt_tags",
    db.Column("prompt_id", db.Integer, db.ForeignKey("prompts.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
    Index("ix_prompt_tags_tag_id", "tag_id"),
)


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    category = db.Column(db.String(20), nullable=False)

    __table_args__ = (
        Index("uq_tags_name_lower", func.lower(name), unique=True),
        CheckConstraint(check_in("category", TagCategory.ALL), name="category_valid"),
    )

    prompts = db.relationship("Prompt", secondary=prompt_tags, back_populates="tags")

    def __repr__(self):
        return f"<Tag {self.name!r} {self.category}>"
