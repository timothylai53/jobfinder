"""Base resume list data (last change, duplicate) and the migrations for the base-resume and run-log columns."""
import sqlite3

from sqlalchemy import create_engine, text

from app import migrations


def _item(client, title, type_="project"):
    return client.post("/api/experience", json={"type": type_, "title": title, "organization": "Syarikat Contoh Bhd",
                                                "start": "", "end": "", "bullets": [], "skills": []}).json()["id"]


def test_base_resume_updated_at_and_duplicate(client):
    a, b = _item(client, "Kedai App"), _item(client, "BSc", "education")
    rid = client.post("/api/resumes", json={"name": "Software", "item_ids": [a, b]}).json()["id"]
    first = next(r for r in client.get("/api/resumes").json() if r["id"] == rid)
    assert first["updated_at"] >= first["created_at"] and first["item_ids"] == [a, b]

    client.put(f"/api/resumes/{rid}", json={"name": "Software roles", "item_ids": [a]})
    after = next(r for r in client.get("/api/resumes").json() if r["id"] == rid)
    assert after["name"] == "Software roles" and after["updated_at"] >= first["updated_at"]

    c1 = client.post(f"/api/resumes/{rid}/duplicate").json()
    c2 = client.post(f"/api/resumes/{rid}/duplicate").json()
    assert (c1["name"], c2["name"]) == ("Software roles (copy)", "Software roles (copy 2)")
    rows = {r["id"]: r for r in client.get("/api/resumes").json()}
    assert rows[c1["id"]]["item_ids"] == [a] and rows[rid]["item_ids"] == [a]  # same selection; the original unchanged
    assert client.post("/api/resumes/999/duplicate").status_code == 404


def test_migration_adds_the_new_columns(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE baseresume (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)")
    con.execute("CREATE TABLE automationrun (id INTEGER PRIMARY KEY, automation_key VARCHAR NOT NULL)")
    con.execute("INSERT INTO automationrun (automation_key) VALUES ('fetch_jobs')")
    con.commit()
    con.close()
    eng = create_engine(f"sqlite:///{db}")
    assert migrations.run(eng) == ["baseresume.updated_at", "automationrun.details", "baseresume.last_used_at"]
    with eng.connect() as c:
        assert c.execute(text("SELECT details FROM automationrun")).scalar() == "[]"


def test_date_parts():
    from models.resume import date_parts
    assert date_parts("2024", "2024") == ["2024"]
    assert date_parts("Jan 2024 ", "jan  2024") == ["Jan 2024"]
    assert date_parts("2023", "2024") == ["2023", "2024"]
    assert date_parts("", "2024") == ["2024"] and date_parts("", "") == []
