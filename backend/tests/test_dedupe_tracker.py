from datetime import date

import pytest

from api.dashboard import response_rate, weekly_counts
from models import Application, StatusHistory
from sources.base import dedupe_key
from sources.manual import extract_from_html


@pytest.mark.parametrize("a,b", [
    (("Acme Sdn Bhd", "Software Engineer", "Kuala Lumpur"), ("ACME SDN. BHD.", "Software Developer", "Kuala Lumpur, Malaysia")),
    (("Acme Berhad", "Jr. Developer (Urgent)", "Penang"), ("Acme", "Junior Developer", "Penang")),
    (("Kedai Tech", "Sr Java Engineer", ""), ("Kedai Tech Pte. Ltd.", "Senior Java Developer", "")),
])
def test_dedupe_key_matches_variants(a, b):
    assert dedupe_key(*a) == dedupe_key(*b)


@pytest.mark.parametrize("a,b", [
    (("Acme", "Software Engineer", "KL"), ("Beta", "Software Engineer", "KL")),
    (("Acme", "Junior Developer", "KL"), ("Acme", "Senior Developer", "KL")),
    (("Acme", "Software Engineer", "Kuala Lumpur"), ("Acme", "Software Engineer", "Penang")),
])
def test_dedupe_key_keeps_different_jobs_apart(a, b):
    assert dedupe_key(*a) != dedupe_key(*b)


def test_extract_jobposting_jsonld():
    html = """<html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting","title":"Graduate Developer",
     "hiringOrganization":{"@type":"Organization","name":"Contoh Sdn Bhd"},
     "jobLocation":{"@type":"Place","address":{"addressLocality":"Cyberjaya","addressCountry":"MY"}},
     "baseSalary":{"currency":"MYR","value":{"minValue":3500,"maxValue":4500}},
     "employmentType":"FULL_TIME",
     "description":"<p>Requirements</p><ul><li>Python</li><li>SQL</li></ul>"}
    </script></head><body>ignored</body></html>"""
    j = extract_from_html(html, "https://example.com/j")
    assert (j.title, j.company, j.location) == ("Graduate Developer", "Contoh Sdn Bhd", "Cyberjaya, MY")
    assert (j.salary_min, j.salary_max, j.salary_currency) == (3500, 4500, "MYR")
    assert "- Python" in j.description and "Requirements" in j.description


def test_extract_generic_html():
    html = "<html><head><meta property='og:site_name' content='Contoh'></head><body><nav>menu</nav>" \
           "<main><h1>QA Engineer</h1><p>We need Selenium.</p></main></body></html>"
    j = extract_from_html(html)
    assert j.title == "QA Engineer" and j.company == "Contoh"
    assert "Selenium" in j.description and "menu" not in j.description


def test_weekly_counts():
    today = date(2026, 11, 7)  # Saturday
    weeks = weekly_counts([date(2026, 11, 2), date(2026, 11, 7), date(2026, 10, 30), date(2026, 1, 1)], today, weeks=3)
    assert [w["week_start"] for w in weeks] == ["2026-10-19", "2026-10-26", "2026-11-02"]
    assert [w["count"] for w in weeks] == [0, 1, 2]


def test_response_rate():
    apps = [Application(id=1, job_id=1, status="Interview", applied_at=date.today()),
            Application(id=2, job_id=2, status="Applied", applied_at=date.today()),
            Application(id=3, job_id=3, status="Saved")]
    hist = [StatusHistory(application_id=1, from_status="Applied", to_status="Interview")]
    assert response_rate(apps, hist) == 50.0
    assert response_rate([apps[2]], []) is None


def test_tracker_service_records_history(client):
    from sqlmodel import Session, select

    from app.db import engine
    from models import Job
    from tracker.service import change_status, create

    with Session(engine) as s:
        job = Job(title="T")
        s.add(job)
        s.flush()
        app = create(s, job.id, "Saved", follow_up_days=5)
        assert change_status(s, app, "Applied", 5, today=date(2026, 11, 1))
        assert app.follow_up_at == date(2026, 11, 6)
        assert not change_status(s, app, "Applied", 5)  # no-op, no history row
        with pytest.raises(ValueError):
            change_status(s, app, "Ghosted")
        s.commit()
        rows = s.exec(select(StatusHistory).where(StatusHistory.application_id == app.id)).all()
        assert [r.to_status for r in rows] == ["Saved", "Applied"]


def test_migration_adds_work_arrangement_to_old_db(tmp_path):
    """An older database without job.work_arrangement gets the column on startup, data intact."""
    import sqlite3

    from sqlalchemy import create_engine

    from app import migrations

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE job (id INTEGER PRIMARY KEY, title VARCHAR NOT NULL)")
    con.execute("INSERT INTO job (title) VALUES ('Old job')")
    con.commit()
    con.close()
    eng = create_engine(f"sqlite:///{db}")
    assert migrations.run(eng) == ["job.work_arrangement", "job.external_ids", "job.high_match_notified"]
    assert migrations.run(eng) == []  # idempotent
    with eng.connect() as c:
        from sqlalchemy import text
        assert c.execute(text("SELECT title, work_arrangement FROM job")).all() == [("Old job", "")]
    eng.dispose()


def test_remote_work_arrangement_counts_as_remote(client):
    p = client.get("/api/profile").json()
    p.update(preferred_locations=["Penang"], remote_ok=True)
    client.put("/api/profile", json=p)
    jid = client.post("/api/jobs/manual", json={"title": "Dev", "location": "Kuala Lumpur", "work_arrangement": "Remote",
                                                "description": "Requirements:\n- Python"}).json()["id"]
    d = client.get(f"/api/jobs/{jid}").json()
    assert d["job"]["work_arrangement"] == "Remote"
    loc = next(i for c in d["match"]["breakdown"]["categories"] for i in c["items"] if i["name"].startswith("Location"))
    assert loc["status"] == "met"
