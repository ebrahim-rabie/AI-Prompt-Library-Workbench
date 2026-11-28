"""Small helpers shared by all layers."""
from datetime import datetime, timezone


def utcnow():
    """Current time in UTC (SRS 2.8: all times are stored in UTC).

    Returned without tzinfo because SQLite does not keep time zones;
    every stored datetime is UTC by convention.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
