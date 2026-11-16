"""SQLite engine and session dependency."""
from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_PATH, ensure_dirs

ensure_dirs()
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def create_db() -> None:
    import models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)
    from app import migrations

    migrations.run(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
