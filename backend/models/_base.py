from datetime import datetime, timezone

from sqlalchemy import JSON, Column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def json_col():
    return Column(JSON, nullable=False, default=list)
