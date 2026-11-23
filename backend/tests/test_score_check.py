"""Score check: rate a job's score, change it, clear it; the report's maths; ratings go with their job; CSV export."""
JD_GOOD = "Junior Python Developer\nRequirements:\n- Python\n- SQL\nFresh graduates welcome."
JD_WEAK = "Senior Java Architect\nRequirements:\n- Java\n- Kubernetes\n- 8 years of experience"


def _job(client, title, jd):
    return client.post("/api/jobs/manual", json={"title": title, "company": "Syarikat Contoh Bhd", "description": jd}).json()["id"]


def _setup(client):
    client.post("/api/resumes/import", json={"name": "Fake", "items": [
        {"type": "work", "title": "Intern", "organization": "Kedai Contoh", "start": "2024", "end": "2024",
         "bullets": ["Built REST APIs in Python with SQL"], "skills": ["Python", "SQL"]}],
        "profile": {"name": "Ali Bin Contoh"}})
    return _job(client, "Junior Python Developer", JD_GOOD), _job(client, "Senior Java Architect", JD_WEAK)


def test_rate_change_and_clear(client):
    good, _ = _setup(client)
    assert client.get(f"/api/jobs/{good}/rating").json() is None
    r = client.put(f"/api/jobs/{good}/rating", json={"rating": "too_high", "note": "  needs Docker really  "}).json()
    score = client.get(f"/api/jobs/{good}").json()["match"]["total"]
    assert (r["rating"], r["note"], r["score_at"]) == ("too_high", "needs Docker really", score)
    r = client.put(f"/api/jobs/{good}/rating", json={"rating": "about_right"}).json()
    assert r["rating"] == "about_right" and r["note"] == ""
    assert client.put(f"/api/jobs/{good}/rating", json={"rating": "meh"}).status_code == 422
    assert client.put("/api/jobs/999/rating", json={"rating": "too_low"}).status_code == 404
    client.delete(f"/api/jobs/{good}/rating")
    assert client.get(f"/api/jobs/{good}/rating").json() is None


def test_report_counts_bands_and_misses(client):
    good, weak = _setup(client)
    empty = client.get("/api/score-check").json()
    assert empty["rated"] == 0 and empty["agree_pct"] is None and empty["misses"] == []
    client.put(f"/api/jobs/{good}/rating", json={"rating": "about_right"})
    client.put(f"/api/jobs/{weak}/rating", json={"rating": "too_high", "note": "Java only"})
    rep = client.get("/api/score-check").json()
    assert (rep["rated"], rep["about_right"], rep["too_high"], rep["too_low"], rep["agree_pct"]) == (2, 1, 1, 0, 50)
    assert sum(b["rated"] for b in rep["bands"]) == 2 and [b["band"] for b in rep["bands"]] == ["0-49", "50-69", "70+"]
    assert [m["job_id"] for m in rep["misses"]] == [weak] and rep["misses"][0]["title"] == "Senior Java Architect"


def test_ratings_go_with_their_job_and_export_as_csv(client):
    good, weak = _setup(client)
    client.put(f"/api/jobs/{good}/rating", json={"rating": "too_low", "note": "=cmd|' /C calc'!A0"})
    client.put(f"/api/jobs/{weak}/rating", json={"rating": "about_right"})
    r = client.get("/api/score-check.csv")
    text = r.content.decode("utf-8-sig")
    assert r.headers["content-type"].startswith("text/csv") and text.splitlines()[0].startswith("job_id,title,company")
    assert "'=cmd" in text  # formula-looking notes stay text
    client.delete(f"/api/jobs/{weak}")
    assert client.get("/api/score-check").json()["rated"] == 1
