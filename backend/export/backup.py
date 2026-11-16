"""Timestamped copy of the SQLite DB into data/backups/ (uses SQLite's online backup, safe while running)."""
import sqlite3
from datetime import datetime
from pathlib import Path


def backup_db(db_path: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    dest = backups_dir / f"jobfinder-{datetime.now():%Y%m%d-%H%M%S}.db"
    n = 1
    while dest.exists():
        dest = backups_dir / f"jobfinder-{datetime.now():%Y%m%d-%H%M%S}-{n}.db"
        n += 1
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest
