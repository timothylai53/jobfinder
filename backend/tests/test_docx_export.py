"""Word export: the same content and order as the PDF, ATS-friendly (real headings, no tables or text boxes),
clickable links in the header. Each test opens the generated .docx with python-docx and reads it back (fake data)."""
import html
import io
import re
import zipfile

import pytest
from docx import Document as open_docx

from tests.test_ai_flow import BANK, JD

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def job(client):
    client.post("/api/resumes/import", json={"name": "Fake", "items": BANK, "profile": {
        "name": "Ali Bin Contoh", "email": "ali.contoh@example.com", "phone": "012-345 6789", "location": "Shah Alam"}})
    profile = client.get("/api/profile").json()
    client.put("/api/profile", json={**profile, "linkedin_url": "linkedin.com/in/ali-contoh", "github_url": "github.com/alicontoh"})
    return client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                                 "description": JD}).json()["id"]


def _resume(client, job_id):
    return client.post("/api/documents/resume", json={
        "job_id": job_id, "summary": "Software engineering graduate.", "skills": ["Python", "SQL", "React"],
        "sections": [{"section": "Experience", "items": [
            {"source_id": "B1", "text": "Developed REST APIs in Python and Flask"},
            {"source_id": "B1", "text": "Wrote SQL queries for weekly reporting"}]},
            {"section": "Projects", "items": [{"source_id": "B2", "text": "Built a React front end with a Node.js backend"}]}],
        "add_original_ids": ["B3", "B4"]}).json()


def _docx(client, doc_id):
    r = client.get(f"/api/documents/{doc_id}/docx")
    assert r.status_code == 200 and r.headers["content-type"] == DOCX
    assert r.headers["content-disposition"].startswith("attachment;") and ".docx" in r.headers["content-disposition"]
    return r.content, open_docx(io.BytesIO(r.content))


def _html_text(client, doc_id) -> str:
    raw = client.get(f"/api/documents/{doc_id}/html").text
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.split("<body>", 1)[1])))


def _in_order(text: str, markers: list[str]) -> bool:
    pos = [text.find(m) for m in markers]
    return -1 not in pos and pos == sorted(pos)


def test_resume_docx_has_the_pdf_content_in_the_pdf_order(client, job):
    doc = _resume(client, job)
    raw, d = _docx(client, doc["id"])
    paras = [p for p in d.paragraphs if p.text.strip()]
    assert paras[0].style.name == "Title" and paras[0].text == "Ali Bin Contoh"
    headings = [p.text for p in paras if p.style.name == "Heading 1"]
    assert headings == ["Summary", "Skills", "Projects", "Experience", "Education", "Certifications"]  # Projects first (default)

    text = "\n".join(p.text for p in paras)
    markers = ["Ali Bin Contoh", "Summary", "Software engineering graduate.", "Skills", "Python, SQL, React",
               "Projects", "Campus Food Ordering App", "Built a React front end with a Node.js backend",
               "Experience", "Software Engineering Intern", "Developed REST APIs in Python and Flask",
               "Wrote SQL queries for weekly reporting", "Education", "Bachelor of Software Engineering",
               "Certifications", "Oracle Certified Associate, Java SE 8 Programmer"]
    assert _in_order(text, markers), "Word order differs from the expected resume order"
    assert _in_order(_html_text(client, doc["id"]), markers), "the PDF layout has the same order"
    assert "Software Engineering Intern, Contoh Tech Sdn Bhd | Jun 2024 - Sep 2024" in text
    assert "Oracle Certified Associate, Java SE 8 Programmer, Oracle (2024)" in text
    bullets = [p.text for p in paras if p.style.name == "List Bullet"]
    assert bullets[:3] == ["Built a React front end with a Node.js backend", "Developed REST APIs in Python and Flask",
                           "Wrote SQL queries for weekly reporting"]


def test_resume_docx_is_ats_friendly_with_clickable_links(client, job):
    raw, d = _docx(client, _resume(client, job)["id"])
    assert d.tables == []
    xml = zipfile.ZipFile(io.BytesIO(raw)).read("word/document.xml").decode("utf-8")
    assert "w:txbxContent" not in xml and "<w:drawing" not in xml and "w:tbl>" not in xml  # no text boxes, images, tables
    links = {r.target_ref for r in d.part.rels.values() if r.reltype.endswith("/hyperlink")}
    assert links == {"https://linkedin.com/in/ali-contoh", "https://github.com/alicontoh"}
    assert "linkedin.com/in/ali-contoh" in xml and "github.com/alicontoh" in xml  # the visible link text
    assert "ali.contoh@example.com | 012-345 6789 | Shah Alam" in [p.text for p in d.paragraphs]


def test_resume_docx_follows_the_projects_first_setting(client, job):
    doc = _resume(client, job)
    s = client.get("/api/settings").json()
    client.put("/api/settings", json={"scoring": s["scoring"], "general": {**s["general"], "resume_projects_first": False}})
    _, d = _docx(client, doc["id"])
    headings = [p.text for p in d.paragraphs if p.style.name == "Heading 1"]
    assert headings.index("Experience") < headings.index("Projects")


def test_cover_letter_docx(client, job):
    letter = client.post("/api/documents/cover-letter", json={
        "job_id": job, "greeting": "Dear Hiring Manager,", "closing": "Sincerely,",
        "paragraphs": ["I am applying for the Junior Software Engineer role.", "I built REST APIs in Python."]}).json()
    raw, d = _docx(client, letter["id"])
    text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
    assert _in_order(text, ["Ali Bin Contoh", "ali.contoh@example.com", "linkedin.com/in/ali-contoh", "Syarikat Contoh Bhd",
                            "Re: Junior Software Engineer", "Dear Hiring Manager,",
                            "I am applying for the Junior Software Engineer role.", "I built REST APIs in Python.",
                            "Sincerely,"])
    assert d.tables == [] and text.rstrip().endswith("Ali Bin Contoh")
    assert any(r.target_ref == "https://linkedin.com/in/ali-contoh" for r in d.part.rels.values())


def test_analyses_have_no_word_version(client, job):
    from sqlmodel import Session

    from app.db import engine
    from documents.service import save_analysis
    with Session(engine) as s:
        doc = save_analysis(s, job, "interview_prep", {"questions": [{"question": "Why us?"}]}, "manual", None)
    assert client.get(f"/api/documents/{doc.id}/docx").status_code == 422
    assert client.get("/api/documents/999999/docx").status_code == 404


def test_docx_is_a4_with_the_pdf_margins_and_real_properties(client, job):
    from docx.shared import Mm

    rid = _resume(client, job)["id"]
    lid = client.post("/api/documents/cover-letter", json={
        "job_id": job, "greeting": "Dear Hiring Manager,", "closing": "Sincerely,", "paragraphs": ["Hello."]}).json()["id"]
    for doc_id in (rid, lid):
        _, d = _docx(client, doc_id)
        sec = d.sections[0]
        assert (round(sec.page_width.mm), round(sec.page_height.mm)) == (210, 297)  # A4, like the PDF
        assert abs(sec.left_margin - Mm(16)) < Mm(0.1) and abs(sec.top_margin - Mm(16)) < Mm(0.1)
        assert d.core_properties.author == "Ali Bin Contoh" and "python-docx" not in d.core_properties.last_modified_by
    assert _docx(client, rid)[1].core_properties.title == "Ali Bin Contoh resume"
    assert _docx(client, lid)[1].core_properties.title.startswith("Cover letter: Junior Software Engineer")
