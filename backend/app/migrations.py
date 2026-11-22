"""Tiny additive migrations: add columns that newer code expects to tables created by older code.

`create_all` creates missing tables but never alters existing ones, so each new column on an
existing table is listed here once. Only additive, defaulted columns; nothing is dropped or rewritten.
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine

# (table, column, SQL type with default)
ADDED_COLUMNS = [
    ("job", "work_arrangement", "VARCHAR NOT NULL DEFAULT ''"),
    ("profile", "years_confirmed", "BOOLEAN NOT NULL DEFAULT 0"),
    ("job", "external_ids", "JSON NOT NULL DEFAULT '{}'"),
    ("job", "high_match_notified", "BOOLEAN NOT NULL DEFAULT 0"),
    ("application", "reminded_on", "DATE"),
    ("profile", "linkedin_url", "VARCHAR NOT NULL DEFAULT ''"),
    ("profile", "github_url", "VARCHAR NOT NULL DEFAULT ''"),
    ("profile", "portfolio_url", "VARCHAR NOT NULL DEFAULT ''"),
    ("baseresume", "updated_at", "DATETIME"),
    ("automationrun", "details", "JSON NOT NULL DEFAULT '[]'"),
]


def run(engine: Engine) -> list[str]:
    done = []
    with engine.begin() as conn:
        for table, column, ddl in ADDED_COLUMNS:
            cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if cols and column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                done.append(f"{table}.{column}")
    return done
