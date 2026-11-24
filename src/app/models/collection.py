"""Collection entity (table: collections) and the collection_prompts link table."""
from sqlalchemy import Index

from ..extensions import db
from ..utils import utcnow

FAVORITES_NAME = "Favorites"

collection_prompts = db.Table(
    "collection_prompts",
    db.Column("collection_id", db.Integer, db.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    db.Column("prompt_id", db.Integer, db.ForeignKey("prompts.id"), primary_key=True),
    db.Column("added_at", db.DateTime, nullable=False, default=utcnow),
)


class Collection(db.Model):
    __tablename__ = "collections"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    # True only for Favorites, which cannot be renamed or deleted (FR-15).
    is_default = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        # Each user has exactly one Favorites collection (partial unique index).
        Index("uq_collections_one_default_per_user", "user_id", unique=True,
              sqlite_where=db.text("is_default = 1"), postgresql_where=db.text("is_default")),
    )

    user = db.relationship("User", back_populates="collections")
    prompts = db.relationship("Prompt", secondary=collection_prompts, lazy="dynamic")

    def __repr__(self):
        return f"<Collection {self.id} {self.name!r}>"
