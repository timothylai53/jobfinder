"""Word (.docx) versions of resumes and cover letters, with python-docx.

Same content and order as the PDF: the resume goes through the PDF's own `layout_resume()` (section order, the
"Projects before Experience" setting, bullets that only repeat their header left out, dates not printed twice).
ATS-friendly: real Heading styles, plain paragraphs and the built-in "List Bullet" style; no tables, text boxes,
columns, headers/footers or images. Profile links are real hyperlinks with the plain address as their text.
"""
import io

from docx import Document as new_docx
from docx.document import Document as Docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph

from documents.render import layout_resume
from models import Document

FONT = "Arial"


def _base() -> Docx:
    d = new_docx()
    normal = d.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(10.5)
    normal.paragraph_format.space_after = Pt(3)
    for name, size in (("Title", 18), ("Heading 1", 11.5)):
        st = d.styles[name]
        st.font.name, st.font.size, st.font.bold = FONT, Pt(size), True
        st.font.color.rgb = RGBColor(0x11, 0x11, 0x11)
    d.styles["Heading 1"].paragraph_format.space_before = Pt(10)
    for section in d.sections:
        section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Pt(45)
    return d


def _hyperlink(p: Paragraph, href: str, text: str) -> None:
    """A real, clickable link (python-docx has no public API for this; this is the documented XML recipe)."""
    rid = p.part.relate_to(href, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    p._p.append(link)


def _contact(d: Docx, header: dict, one_line: bool) -> None:
    plain = [x for x in (header.get("email"), header.get("phone"), header.get("location")) if x]
    links = header.get("links") or []
    if one_line:
        if plain:
            d.add_paragraph(" | ".join(plain))
        if links:
            p = d.add_paragraph()
            for i, link in enumerate(links):
                if i:
                    p.add_run(" | ")
                _hyperlink(p, link["href"], link["text"])
    else:
        for line in plain:
            d.add_paragraph(line).paragraph_format.space_after = Pt(0)
        for link in links:
            _hyperlink(d.add_paragraph(), link["href"], link["text"])


def resume_docx(doc: Document, projects_first: bool = True) -> bytes:
    c = layout_resume(doc.content, projects_first)
    d = _base()
    header = c.get("header") or {}
    d.add_paragraph(header.get("name") or "Your Name", style="Title")
    _contact(d, header, one_line=True)
    if c.get("summary"):
        d.add_heading("Summary", level=1)
        d.add_paragraph(c["summary"])
    if c.get("skills"):
        d.add_heading("Skills", level=1)
        d.add_paragraph(", ".join(c["skills"]))
    for sec in c.get("sections", []):
        d.add_heading(sec["section"], level=1)
        for e in sec["entries"]:
            p = d.add_paragraph()
            p.paragraph_format.keep_with_next = True  # the entry's header stays with its first bullet
            p.add_run(e["title"]).bold = True
            if e.get("organization"):
                p.add_run(f", {e['organization']}")
            dates = e.get("dates") or []
            if e["type"] in ("certification", "publication") and not e.get("bullets"):
                if dates:
                    p.add_run(f" ({dates[-1]})")
            elif dates:
                p.add_run(f" | {' - '.join(dates)}")
            for b in e.get("bullets", []):
                d.add_paragraph(b, style="List Bullet")
    return _save(d)


def cover_letter_docx(doc: Document) -> bytes:
    c = doc.content
    d = _base()
    header = c.get("header") or {}
    name = d.add_paragraph()
    name.add_run(header.get("name") or "Your Name").bold = True
    name.paragraph_format.space_after = Pt(0)
    _contact(d, header, one_line=False)
    d.add_paragraph()
    for line in (c.get("date"), c.get("company"), f"Re: {c.get('role', '')}"):
        if line:
            d.add_paragraph(line).paragraph_format.space_after = Pt(0)
    d.add_paragraph()
    d.add_paragraph(c.get("greeting") or "Dear Hiring Manager,")
    for para in c.get("paragraphs", []):
        d.add_paragraph(para).alignment = WD_ALIGN_PARAGRAPH.LEFT
    d.add_paragraph(c.get("closing") or "Sincerely,")
    d.add_paragraph(header.get("name") or "")
    return _save(d)


def _save(d: Docx) -> bytes:
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def docx_for(doc: Document, projects_first: bool = True) -> bytes:
    if doc.type == "resume":
        return resume_docx(doc, projects_first)
    if doc.type == "cover_letter":
        return cover_letter_docx(doc)
    raise ValueError(f"{doc.type} documents have no printable layout")
