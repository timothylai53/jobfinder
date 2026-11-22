"""HTML (Jinja2) and PDF (Playwright, headless Chromium) rendering for resumes and cover letters.

The page is rendered offline: every network request from it is blocked, and nothing but the HTML string is loaded.
PDFs are stored under data/documents/<job_id>/.
"""
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import Document
from models.resume import date_parts

TEMPLATES = Path(__file__).resolve().parent / "templates"
_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]), trim_blocks=True,
                   lstrip_blocks=True)
RENDERABLE = ("resume", "cover_letter")


class PdfUnavailable(Exception):
    pass


_STOP = {"a", "an", "the", "and", "of", "in", "at", "for", "to", "with", "on", "by"}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP]


def repeats(text: str, header_words: set[str]) -> bool:
    """True if (nearly) every word of `text` is already in the header: at most 1 in 10 words is new."""
    words = _words(text)
    return bool(words) and sum(w in header_words for w in words) >= 0.9 * len(words)


def layout_entry(e: dict) -> dict:
    """Print each fact once: dates the title/organization already contain aren't printed again, and a bullet
    that only repeats the header ("Semester 2, Session 2022/2023" under a title that says so) is left out."""
    named = set(_words(f"{e.get('title', '')} {e.get('organization', '')}"))
    dates = date_parts(e.get("start", ""), e.get("end", ""))
    header = named | {w for d in dates for w in _words(d)}
    return {**e, "dates": [d for d in dates if not set(_words(d)) <= named],
            "bullets": [b for b in e.get("bullets", []) if not repeats(b, header)]}


def layout_resume(content: dict, projects_first: bool = True) -> dict:
    """Layout choices applied when printing, so they reach every version: section order and repeated text."""
    sections = [{**s, "entries": [layout_entry(e) for e in s.get("entries", [])]} for s in content.get("sections", [])]
    names = [s["section"] for s in sections]
    if projects_first and "Projects" in names and "Experience" in names and names.index("Experience") < names.index("Projects"):
        sections.insert(names.index("Experience"), sections.pop(names.index("Projects")))
    return {**content, "sections": sections}


def html_for(doc: Document, projects_first: bool = True) -> str:
    if doc.type not in RENDERABLE:
        raise ValueError(f"{doc.type} documents have no printable layout")
    content = layout_resume(doc.content, projects_first) if doc.type == "resume" else doc.content
    return _env.get_template(f"{doc.type}.html").render(**content)


def pdf_path_for(doc: Document) -> Path:
    from app.config import DATA_DIR
    safe = re.sub(r"[^a-z0-9]+", "-", (doc.content.get("header", {}).get("name") or "").lower()).strip("-")
    name = f"{doc.type.replace('_', '-')}-v{doc.version}" + (f"-{safe}" if safe else "") + ".pdf"
    return DATA_DIR / "documents" / str(doc.job_id or "general") / name


def html_to_pdf(html: str, out: Path) -> Path:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise PdfUnavailable("PDF export needs Playwright. Run setup.bat (it installs Playwright and Chromium).") from e
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.route("**/*", lambda route: route.abort())  # offline: the HTML is self-contained
                page.set_content(html, wait_until="load")
                page.pdf(path=str(out), format="A4", print_background=False, prefer_css_page_size=True)
            finally:
                browser.close()
    except PlaywrightError as e:
        msg = str(e).splitlines()[0]
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            msg = "Chromium for Playwright is not installed. Run setup.bat, or: .venv\\Scripts\\python -m playwright install chromium"
        raise PdfUnavailable(msg) from e
    return out
