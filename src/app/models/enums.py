"""Allowed values of the enumeration columns (Design 4.2.2, below Figure 3).

Columns are stored as VARCHAR with a CHECK constraint, exactly as in the
data dictionary, so the same schema works on SQLite and PostgreSQL.
"""


class Role:
    REGISTERED = "Registered"
    ADMINISTRATOR = "Administrator"
    ALL = (REGISTERED, ADMINISTRATOR)


class AccountStatus:
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    ALL = (ACTIVE, SUSPENDED)


class PromptStatus:
    DRAFT = "Draft"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"
    HIDDEN = "Hidden"
    ALL = (DRAFT, PUBLISHED, ARCHIVED, HIDDEN)


class TargetModel:
    GENERAL = "General"
    GPT = "GPT"
    CLAUDE = "Claude"
    GEMINI = "Gemini"
    OTHER = "Other"
    ALL = (GENERAL, GPT, CLAUDE, GEMINI, OTHER)


class VarType:
    TEXT = "Text"
    LONG_TEXT = "LongText"
    NUMBER = "Number"
    ALL = (TEXT, LONG_TEXT, NUMBER)


class TagCategory:
    DOMAIN = "Domain"
    TASK = "Task"
    ALL = (DOMAIN, TASK)


class ReviewStatus:
    VISIBLE = "Visible"
    HIDDEN = "Hidden"
    ALL = (VISIBLE, HIDDEN)


class ReportReason:
    SPAM = "Spam"
    INAPPROPRIATE = "Inappropriate content"
    COPYRIGHT = "Copyright"
    OTHER = "Other"
    ALL = (SPAM, INAPPROPRIATE, COPYRIGHT, OTHER)


class ReportStatus:
    PENDING = "Pending"
    RESOLVED = "Resolved"
    ALL = (PENDING, RESOLVED)


class ActionType:
    DISMISS = "Dismiss"
    HIDE = "Hide"
    SUSPEND = "Suspend"
    ALL = (DISMISS, HIDE, SUSPEND)


def check_in(column, values):
    """SQL text for a CHECK constraint: column IN ('a', 'b', ...)."""
    quoted = ", ".join("'" + value.replace("'", "''") + "'" for value in values)
    return f"{column} IN ({quoted})"
