from datetime import UTC, datetime

from sqlalchemy import JSON, Column


def utcnow() -> datetime:
    return datetime.now(UTC)


def require_id(row) -> int:
    """The primary key of a row read from (or flushed to) the database. SQLModel types `id` as optional because it is
    None before the first flush; past that point a missing id is a bug, so say so loudly instead of passing None on."""
    if row.id is None:
        raise ValueError(f"{type(row).__name__} has no id yet (not saved)")
    return row.id


def json_col():
    return Column(JSON, nullable=False, default=list)
