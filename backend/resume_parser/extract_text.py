"""PDF / DOCX -> plain text (one line per visual line)."""
from pathlib import Path

import pdfplumber
from docx import Document


class UnsupportedFile(Exception):
    pass


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf(path)
    if suffix == ".docx":
        return _docx(path)
    raise UnsupportedFile(f"Unsupported file type {suffix!r}; upload a .pdf or .docx")


def _pdf(path: Path) -> str:
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text(x_tolerance=1.5, y_tolerance=3) or "")
    return "\n".join(pages).strip()


def _docx(path: Path) -> str:
    doc = Document(str(path))
    lines: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        lines.append(("- " + text) if "list" in style else text)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            # merged cells repeat their text; keep unique cells in order
            lines.append(" | ".join(dict.fromkeys(cells)))
    return "\n".join(lines).strip()
