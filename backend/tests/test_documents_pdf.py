"""PDF export: real Playwright + Chromium, fully offline (the page's network requests are all blocked).
Checks the PDF has selectable text with standard headings (ATS-friendly). Skipped if Chromium isn't installed."""
import pdfplumber
import pytest

from tests.test_ai_flow import BANK, JD


@pytest.fixture
def job(client):
    client.post("/api/resumes/import", json={"name": "Fake", "items": BANK,
                                             "profile": {"name": "Ali Bin Contoh", "email": "ali.contoh@example.com"}})
    return client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                                 "description": JD}).json()["id"]


def _pdf_or_skip(client, doc_id):
    r = client.get(f"/api/documents/{doc_id}/pdf")
    if r.status_code == 503:
        pytest.skip(r.json()["detail"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    return r


def test_resume_pdf_has_selectable_text_and_standard_headings(client, job, tmp_path):
    body = {"job_id": job, "summary": "Software engineering graduate.", "skills": ["Python", "SQL"],
            "sections": [{"section": "Experience", "items": [{"source_id": "B1", "text": "Developed REST APIs in Python"}]},
                         {"section": "Certifications", "items": [{"source_id": "B4", "text": "Oracle Certified Associate, Java SE 8 Programmer"}]},
                         {"section": "Publications", "items": [{"source_id": "B5", "text": "A Study of Queue Scheduling in Campus Systems"}]}],
            "add_original_ids": ["B3"]}
    doc = client.post("/api/documents/resume", json=body).json()
    r = _pdf_or_skip(client, doc["id"])
    f = tmp_path / "r.pdf"
    f.write_bytes(r.content)
    with pdfplumber.open(f) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    for s in ("Ali Bin Contoh", "SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION", "CERTIFICATIONS", "PUBLICATIONS",
              "Software Engineering Intern", "Developed REST APIs in Python", "Oracle Certified Associate"):
        assert s in text, s
    stored = client.get(f"/api/documents/{doc['id']}").json()
    assert stored["has_pdf"] and f"documents\\{job}\\" in stored["pdf_path"].replace("/", "\\")  # data/documents/<job_id>/


def test_cover_letter_pdf(client, job):
    doc = client.post("/api/documents/cover-letter", json={"job_id": job, "greeting": "Dear Hiring Manager,",
                                                           "paragraphs": ["I am applying."], "closing": "Sincerely,"}).json()
    _pdf_or_skip(client, doc["id"])


def test_analysis_documents_have_no_pdf(client, job):
    from app.db import engine
    from documents.service import save_analysis
    from sqlmodel import Session
    with Session(engine) as s:
        doc = save_analysis(s, job, "interview_prep", {"questions": [{"question": "Why us?"}]}, "manual", None)
    assert client.get(f"/api/documents/{doc.id}/pdf").status_code == 422


def test_profile_links_are_clickable_text_in_pdfs(client, job, tmp_path):
    profile = client.get("/api/profile").json()
    client.put("/api/profile", json={**profile, "linkedin_url": "linkedin.com/in/ali-contoh",
                                     "portfolio_url": "https://alicontoh.example.com/"})
    resume = client.post("/api/documents/resume", json={"job_id": job, "add_original_ids": ["B1"]}).json()
    letter = client.post("/api/documents/cover-letter", json={"job_id": job, "greeting": "Dear Hiring Manager,",
                                                              "paragraphs": ["I am applying."], "closing": "Sincerely,"}).json()
    for doc in (resume, letter):
        f = tmp_path / f"{doc['id']}.pdf"
        f.write_bytes(_pdf_or_skip(client, doc["id"]).content)
        with pdfplumber.open(f) as pdf:
            text = pdf.pages[0].extract_text()
            uris = {h["uri"] for h in pdf.pages[0].hyperlinks}
        assert "linkedin.com/in/ali-contoh" in text and "alicontoh.example.com" in text  # plain, selectable text
        assert {"https://linkedin.com/in/ali-contoh", "https://alicontoh.example.com/"} <= uris  # and clickable
