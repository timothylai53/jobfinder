"""Timestamped copies of the SQLite DB in data/backups/ (SQLite's online backup, safe while the app runs).

Two kinds, told apart by name:
- jobfinder-YYYYMMDD-HHMMSS.db       manual ("Backup database now", and before "Clear bank"). Never deleted.
- jobfinder-auto-YYYYMMDD-HHMMSS.db  the automatic daily backup made at startup. Only the newest KEEP_AUTO are kept.
- jobfinder-before-restore-….db      made just before a restore replaces the data. Counted as manual: never deleted.

Restoring (restore_backup) copies a chosen backup over the live database with SQLite's backup API, which is safe with
WAL mode and open connections, after checking the file and saving the current data first.
"""
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

MANUAL_PREFIX = "jobfinder-"
AUTO_PREFIX = "jobfinder-auto-"
BEFORE_RESTORE_PREFIX = "jobfinder-before-restore-"
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


# A backup is chosen by name only, and the name must look like one of ours: no folders, no "..", no other files.
BACKUP_NAME = re.compile(r"^jobfinder-[A-Za-z0-9-]+\.db$")
# Tables a JobFinder database always has; a file without them is not one of ours (or is too damaged to use).
REQUIRED_TABLES = {"job", "profile", "experienceitem", "application"}


class BackupError(ValueError):
    """The chosen backup can't be used; the message says why, in plain words."""


def list_backups(backups_dir: Path) -> list[dict]:
    """Every backup, newest first, with its kind (automatic / manual / before restore) and size."""
    if not backups_dir.exists():
        return []
    out = []
    for f in sorted(backups_dir.glob(f"{MANUAL_PREFIX}*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not BACKUP_NAME.match(f.name):
            continue
        kind = ("automatic" if f.name.startswith(AUTO_PREFIX) else
                "before restore" if f.name.startswith(BEFORE_RESTORE_PREFIX) else "manual")
        st = f.stat()
        out.append({"name": f.name, "kind": kind, "size": st.st_size,
                    "created_at": datetime.fromtimestamp(st.st_mtime).isoformat()})
    return out


def check_backup(path: Path) -> None:
    """Refuse anything that isn't a readable, intact JobFinder database."""
    try:
        con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        raise BackupError(f"{path.name} is not a readable database ({e}).") from e
    if not ok or ok[0] != "ok":
        raise BackupError(f"{path.name} is damaged (SQLite integrity check: {ok[0] if ok else 'no answer'}).")
    missing = REQUIRED_TABLES - tables
    if missing:
        raise BackupError(f"{path.name} is not a JobFinder database (missing: {', '.join(sorted(missing))}).")


def restore_backup(name: str, db_path: Path, backups_dir: Path) -> Path:
    """Replace the live data with backup `name`. Saves the current data as a before-restore backup first and returns
    that file. The caller disposes its connection pool before and runs the migrations after."""
    if not BACKUP_NAME.match(name):
        raise BackupError("Choose one of the backups in the list.")
    src_path = backups_dir / name
    if not src_path.is_file() or src_path.resolve().parent != backups_dir.resolve():
        raise BackupError(f"There is no backup called {name}.")
    check_backup(src_path)
    saved = backup_db(db_path, backups_dir, BEFORE_RESTORE_PREFIX)
    src = sqlite3.connect(f"{src_path.resolve().as_uri()}?mode=ro", uri=True)
    dst = sqlite3.connect(db_path, timeout=30)
    try:
        src.backup(dst)  # page by page, inside SQLite's own locking: no half-written file if it fails
    finally:
        dst.close()
        src.close()
    return saved
