"""Timestamped copies of the SQLite DB in data/backups/ (SQLite's online backup, safe while the app runs).

Two kinds, told apart by name:
- jobfinder-YYYYMMDD-HHMMSS.db       manual ("Backup database now", and before "Clear bank"). Never deleted.
- jobfinder-auto-YYYYMMDD-HHMMSS.db  the automatic daily backup made at startup. Only the newest KEEP_AUTO are kept.
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path

MANUAL_PREFIX = "jobfinder-"
AUTO_PREFIX = "jobfinder-auto-"
KEEP_AUTO = 14


def backup_db(db_path: Path, backups_dir: Path, prefix: str = MANUAL_PREFIX, now: datetime | None = None) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{now or datetime.now():%Y%m%d-%H%M%S}"
    dest = backups_dir / f"{prefix}{stamp}.db"
    n = 1
    while dest.exists():
        dest = backups_dir / f"{prefix}{stamp}-{n}.db"
        n += 1
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest


def _auto_backups(backups_dir: Path) -> list[Path]:
    """Automatic backups, newest first (the timestamp in the name sorts correctly)."""
    return sorted(backups_dir.glob(f"{AUTO_PREFIX}*.db"), key=lambda p: p.name, reverse=True)


def prune_auto(backups_dir: Path, keep: int = KEEP_AUTO) -> list[Path]:
    """Delete automatic backups beyond the newest `keep`. Manual backups are never touched."""
    removed = _auto_backups(backups_dir)[keep:]
    for p in removed:
        p.unlink(missing_ok=True)
    return removed


def daily_backup(db_path: Path, backups_dir: Path, today: date | None = None) -> Path | None:
    """At most one automatic backup per day. Returns the new file, or None if today's exists or there is no DB yet.
    The day that is checked and the day in the new file's name come from the same moment, so they always agree."""
    if not db_path.exists():
        return None
    now = datetime.combine(today, datetime.now().time()) if today else datetime.now()
    if backups_dir.exists() and any(p.name.startswith(f"{AUTO_PREFIX}{now:%Y%m%d}") for p in _auto_backups(backups_dir)):
        return None
    dest = backup_db(db_path, backups_dir, AUTO_PREFIX, now)
    prune_auto(backups_dir)
    return dest


def backup_status(backups_dir: Path) -> dict:
    """For Settings: the newest backup of any kind, and how many automatic ones are kept."""
    files = sorted(backups_dir.glob(f"{MANUAL_PREFIX}*.db"), key=lambda p: p.stat().st_mtime, reverse=True) \
        if backups_dir.exists() else []
    last = files[0] if files else None
    return {
        "last_backup_at": datetime.fromtimestamp(last.stat().st_mtime).isoformat() if last else None,
        "last_backup_name": last.name if last else None,
        "last_backup_automatic": bool(last and last.name.startswith(AUTO_PREFIX)),
        "automatic_kept": len(_auto_backups(backups_dir)) if backups_dir.exists() else 0,
        "keep_automatic": KEEP_AUTO,
    }
