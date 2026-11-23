"""Restoring a backup from the app: a round trip, the current data saved first, bad or foreign files and odd names
refused, and an older backup brought up to the current schema."""
import sqlite3

from app import config

JD = "Junior Python Developer\nRequirements:\n- Python"


def _job(client, title):
    return client.post("/api/jobs/manual", json={"title": title, "company": "Syarikat Contoh Bhd", "description": JD}).json()["id"]


def _titles(client):
    return sorted(j["title"] for j in client.get("/api/jobs").json())


def test_restore_round_trip_saves_the_current_data_first(client):
    _job(client, "Kept Job")
    name = client.post("/api/backup").json()["name"]
    _job(client, "Added After Backup")
    assert _titles(client) == ["Added After Backup", "Kept Job"]

    r = client.post(f"/api/backups/{name}/restore")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["restored"] == name and body["saved_current_as"].startswith("jobfinder-before-restore-")
    assert _titles(client) == ["Kept Job"]  # back to the backup
    assert client.get("/api/jobs").json()[0]["score"] is not None  # rescored with today's rules

    listed = {b["name"]: b["kind"] for b in client.get("/api/backups").json()}
    assert listed[name] == "manual" and listed[body["saved_current_as"]] == "before restore"
    con = sqlite3.connect(config.BACKUPS_DIR / body["saved_current_as"])  # the data that was replaced is safe
    assert {t for (t,) in con.execute("SELECT title FROM job")} == {"Kept Job", "Added After Backup"}
    con.close()


def _before_restore_count(client):
    return sum(b["kind"] == "before restore" for b in client.get("/api/backups").json())


def test_damaged_or_foreign_files_are_refused_and_nothing_changes(client):
    _job(client, "Still Here")
    saved_before = _before_restore_count(client)
    (config.BACKUPS_DIR / "jobfinder-garbage.db").write_bytes(b"this is not sqlite at all" * 100)
    foreign = sqlite3.connect(config.BACKUPS_DIR / "jobfinder-foreign.db")
    foreign.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT)")
    foreign.commit()
    foreign.close()
    r = client.post("/api/backups/jobfinder-garbage.db/restore")
    assert r.status_code == 422 and "not a readable database" in r.json()["detail"]
    r = client.post("/api/backups/jobfinder-foreign.db/restore")
    assert r.status_code == 422 and "not a JobFinder database" in r.json()["detail"]
    assert _titles(client) == ["Still Here"]
    assert _before_restore_count(client) == saved_before  # refused before anything was saved or touched


def test_only_backups_in_the_folder_by_their_own_names(client):
    for bad in ("jobfinder.db", "notes.db", "jobfinder-nope.db", "jobfinder-..db", "..%2Fjobfinder.db"):
        r = client.post(f"/api/backups/{bad}/restore")
        assert r.status_code in (404, 422), (bad, r.status_code)


def test_an_older_backup_gets_the_newer_tables_and_columns(client):
    _job(client, "Old Version Job")
    name = client.post("/api/backup").json()["name"]
    old = sqlite3.connect(config.BACKUPS_DIR / name)  # make it look like a backup from before these existed
    old.execute("DROP TABLE scorerating")
    old.execute("ALTER TABLE baseresume DROP COLUMN last_used_at")
    old.commit()
    old.close()
    assert client.post(f"/api/backups/{name}/restore").status_code == 200
    con = sqlite3.connect(config.DB_PATH)
    tables = {t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    cols = {c[1] for c in con.execute("PRAGMA table_info(baseresume)")}
    con.close()
    assert "scorerating" in tables and "last_used_at" in cols
    job_id = client.get("/api/jobs").json()[0]["id"]
    assert client.put(f"/api/jobs/{job_id}/rating", json={"rating": "about_right"}).status_code == 200
