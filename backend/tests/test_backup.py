"""Automatic daily backup at startup: one per day, newest 14 kept, manual backups never deleted (fake temp DBs)."""
import sqlite3
from datetime import date

from export.backup import AUTO_PREFIX, backup_status, daily_backup, prune_auto


def _db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (x INTEGER)")
    con.execute("INSERT INTO t VALUES (42)")
    con.commit()
    con.close()
    return path


def test_one_automatic_backup_per_day_and_it_is_a_real_copy(tmp_path):
    db, out = _db(tmp_path / "jobfinder.db"), tmp_path / "backups"
    first = daily_backup(db, out, date(2026, 11, 20))
    assert first is not None and first.name.startswith(AUTO_PREFIX)
    assert sqlite3.connect(first).execute("SELECT x FROM t").fetchone() == (42,)
    assert daily_backup(db, out, date(2026, 11, 20)) is None  # same day: nothing new


def test_keeps_the_newest_14_automatic_and_every_manual_backup(tmp_path):
    out = tmp_path / "backups"
    out.mkdir()
    for d in range(1, 21):
        (out / f"{AUTO_PREFIX}202611{d:02d}-080000.db").write_bytes(b"x")
    (out / "jobfinder-20261101-120000.db").write_bytes(b"manual")
    removed = prune_auto(out)
    assert len(removed) == 6 and all(p.name < f"{AUTO_PREFIX}20261107" for p in removed)
    assert len(list(out.glob(f"{AUTO_PREFIX}*.db"))) == 14
    assert (out / "jobfinder-20261101-120000.db").exists()


def test_no_database_yet_means_no_backup(tmp_path):
    assert daily_backup(tmp_path / "missing.db", tmp_path / "backups") is None


def test_status_reports_the_last_backup(tmp_path, client):
    out = tmp_path / "backups"
    assert backup_status(out)["last_backup_at"] is None
    daily_backup(_db(tmp_path / "jobfinder.db"), out)
    s = backup_status(out)
    assert s["last_backup_automatic"] is True and s["automatic_kept"] == 1 and s["keep_automatic"] == 14
    assert set(client.get("/api/backup/status").json()) >= {"last_backup_at", "automatic_kept"}
