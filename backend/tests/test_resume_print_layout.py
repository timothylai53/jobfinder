"""Resume print layout (fake data): Projects before Experience setting, bullets that only repeat their header,
and dates the title or organization already contain."""
from documents.render import layout_entry, layout_resume, repeats
from tests.test_ai_flow import BANK, JD


def _entry(**kw):
    return {"source_id": "B1", "type": "achievement", "title": "", "organization": "", "start": "", "end": "",
            "bullets": [], **kw}


def test_bullet_repeating_the_header_is_dropped():
    e = layout_entry(_entry(title="Placed second and won the Silver Award at Contoh Expo 2024", organization="Contoh Expo",
                            end="2024", bullets=["Placed second and won the Silver Award",
                                                 "Built a campus queue simulator in Python"]))
    assert e["bullets"] == ["Built a campus queue simulator in Python"]
    e = layout_entry(_entry(type="education", title="Dean's List, Semester 2, Session 2022/2023",
                            organization="Universiti Contoh", bullets=["Semester 2, Session 2022/2023"]))
    assert e["bullets"] == []


def test_bullet_with_new_facts_is_kept():
    header = {"silver", "award", "contoh", "expo", "2024"}
    assert not repeats("Won the Silver Award for a real-time bus tracker built with 3 teammates", header)
    assert repeats("Silver Award, Contoh Expo 2024.", header)
    assert not repeats("", header)


def test_date_already_in_title_or_organization_is_not_printed_again():
    assert layout_entry(_entry(type="certification", title="Silver Award", organization="Contoh Expo 2024", end="2024"))["dates"] == []
    assert layout_entry(_entry(title="Session 2023/2024", start="2023", end="2024"))["dates"] == []
    assert layout_entry(_entry(title="Intern", organization="Contoh Tech", start="Jun 2024", end="Sep 2024"))["dates"] == ["Jun 2024", "Sep 2024"]
    assert layout_entry(_entry(title="App", start="2023", end="2023"))["dates"] == ["2023"]  # same year once


def test_projects_first_moves_only_projects():
    content = {"sections": [{"section": s, "entries": []} for s in ("Experience", "Education", "Projects", "Certifications")]}
    on = [s["section"] for s in layout_resume(content, projects_first=True)["sections"]]
    off = [s["section"] for s in layout_resume(content, projects_first=False)["sections"]]
    assert on == ["Projects", "Experience", "Education", "Certifications"]
    assert off == ["Experience", "Education", "Projects", "Certifications"]


def test_setting_defaults_on_and_drives_the_printed_order(client):
    client.post("/api/resumes/import", json={"name": "Fake", "items": BANK, "profile": {"name": "Ali Bin Contoh"}})
    job = client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                                "description": JD}).json()["id"]
    doc = client.post("/api/documents/resume", json={"job_id": job, "add_original_ids": ["B1", "B2"]}).json()
    s = client.get("/api/settings").json()
    assert s["general"]["resume_projects_first"] is True
    html = client.get(f"/api/documents/{doc['id']}/html").text
    assert html.index(">Projects<") < html.index(">Experience<")
    client.put("/api/settings", json={"scoring": s["scoring"], "general": {**s["general"], "resume_projects_first": False}})
    html = client.get(f"/api/documents/{doc['id']}/html").text
    assert html.index(">Experience<") < html.index(">Projects<")
    assert doc["content"]["sections"][0]["section"] == "Experience"  # the saved version itself is unchanged


def test_printed_html_has_no_repeated_year(client):
    client.post("/api/resumes/import", json={"name": "Fake", "profile": {"name": "Ali Bin Contoh"}, "items": [
        {"type": "achievement", "title": "Silver Award", "organization": "Contoh Expo 2024", "start": "", "end": "2024",
         "bullets": ["Silver Award, Contoh Expo 2024"], "skills": []}]})
    job = client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                                "description": JD}).json()["id"]
    doc = client.post("/api/documents/resume", json={"job_id": job, "add_original_ids": ["B1"]}).json()
    html = client.get(f"/api/documents/{doc['id']}/html").text
    assert "Contoh Expo 2024" in html and "(2024)" not in html and "<li>Silver Award, Contoh Expo 2024</li>" not in html
