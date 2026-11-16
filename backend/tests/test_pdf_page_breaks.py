"""PDF page breaks with a long fake resume (real Playwright + Chromium, offline): a section heading is never the
last line of a page, and an entry header is never separated from its first bullet."""
import pdfplumber
import pytest

from documents import render
from models import Document

HEADINGS = {"SUMMARY", "SKILLS", "PROJECTS", "EXPERIENCE", "EDUCATION", "CERTIFICATIONS", "ACHIEVEMENTS"}


def _entry(kind: str, n: int, bullets: int) -> dict:
    return {"source_id": f"B{n}", "type": kind, "title": f"Fake {kind} title {n}", "organization": "Contoh Sdn Bhd",
            "start": "2023", "end": "2024",
            "bullets": [f"Fake bullet {n}.{b} describing work done with enough words to fill a line" for b in range(bullets)]}


def _resume(lead: int) -> Document:
    """`lead` lines of filler in the summary shift every later break, so the variants together put a heading
    and an entry header near the bottom of a page."""
    sections = [
        {"section": "Projects", "entries": [_entry("project", i, 3) for i in range(1, 5)]},
        {"section": "Experience", "entries": [_entry("work", i, 4) for i in range(5, 9)]},
        {"section": "Education", "entries": [_entry("education", i, 2) for i in range(9, 11)]},
        {"section": "Achievements", "entries": [_entry("achievement", i, 1) for i in range(11, 15)]},
    ]
    content = {"header": {"name": "Ali Bin Contoh", "email": "ali.contoh@example.com", "links": []},
               "summary": " ".join(["Fake summary sentence that takes up some room."] * (6 * lead + 1)),
               "skills": ["Python", "SQL"], "sections": sections}
    return Document(id=1, job_id=1, type="resume", version=1, content=content, source="manual")


def _lines(page) -> list[str]:
    return [ln.strip() for ln in (page.extract_text() or "").splitlines() if ln.strip()]


@pytest.mark.parametrize("lead", range(0, 12))
def test_headings_and_entry_headers_stay_with_their_content(tmp_path, lead):
    out = tmp_path / "r.pdf"
    try:
        render.html_to_pdf(render.html_for(_resume(lead)), out)
    except render.PdfUnavailable as e:
        pytest.skip(str(e))
    with pdfplumber.open(out) as pdf:
        pages = [_lines(p) for p in pdf.pages]
    assert len(pages) >= 2
    for i, lines in enumerate(pages[:-1]):
        last = lines[-1]
        assert last not in HEADINGS, f"page {i + 1} ends with the heading {last!r}"
        assert not last.startswith("Fake ") or "bullet" in last, f"page {i + 1} ends with the entry header {last!r}"


@pytest.mark.parametrize("lead", range(0, 8))
def test_entry_taller_than_a_page_keeps_header_with_first_bullet(tmp_path, lead):
    doc = _resume(lead)
    doc.content["sections"][1]["entries"][0]["bullets"] = [f"Fake bullet long.{b} with filler words" for b in range(70)]
    out = tmp_path / "r.pdf"
    try:
        render.html_to_pdf(render.html_for(doc), out)
    except render.PdfUnavailable as e:
        pytest.skip(str(e))
    with pdfplumber.open(out) as pdf:
        pages = [_lines(p) for p in pdf.pages]
    for i, lines in enumerate(pages[:-1]):
        assert lines[-1] not in HEADINGS and (not lines[-1].startswith("Fake ") or "bullet" in lines[-1]), (i, lines[-1])
