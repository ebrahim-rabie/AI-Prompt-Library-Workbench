"""Model layer: ORM entities (Design 4.1.2, Figure 16).

Importing this package registers all 10 tables plus the 2 link tables.
"""
from .collection import FAVORITES_NAME, Collection, collection_prompts
from .feedback import Rating, Review
from .moderation import ModerationAction, Report
from .prompt import Prompt, PromptVariable, PromptVersion
from .tag import Tag, prompt_tags
from .user import User

__all__ = [
    "User",
    "Prompt",
    "PromptVersion",
    "PromptVariable",
    "Tag",
    "prompt_tags",
    "Collection",
    "collection_prompts",
    "FAVORITES_NAME",
    "Rating",
    "Review",
    "Report",
    "ModerationAction",
]
