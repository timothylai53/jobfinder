"""Build fake resume files for tests (no real personal data)."""
from pathlib import Path

from docx import Document

FAKE_RESUME_LINES = [
    "Aisyah Tan",
    "aisyah.tan@example.com | +60 12-345 6789 | Petaling Jaya, Selangor",
    "SUMMARY",
    "Final-year Software Engineering student who enjoys building web apps.",
    "EDUCATION",
    "Bachelor of Software Engineering (Hons) | Universiti Contoh Malaysia",
    "Sep 2023 - Present",
    "- CGPA 3.70, expected graduation Jun 2027",
    "WORK EXPERIENCE",
    "Software Engineering Intern | Kedai Tech Sdn Bhd",
    "Jun 2025 - Sep 2025",
    "- Built internal dashboards with React and TypeScript",
    "- Wrote REST APIs in Python (FastAPI) backed by PostgreSQL",
    "PROJECTS",
    "Campus Food Ordering App",
    "Jan 2025 - Apr 2025",
    "- Flutter mobile app with Firebase authentication",
    "- Led a team of 4 using Scrum",
    "SKILLS",
    "Python, Java, JavaScript, React, SQL, Git, Docker",
    "LANGUAGES",
    "English, Bahasa Malaysia, Mandarin",
]


def make_docx(path: Path, lines: list[str] = FAKE_RESUME_LINES) -> Path:
    doc = Document()
    for line in lines:
        if line.startswith("- "):
            doc.add_paragraph(line[2:], style="List Bullet")
        else:
            doc.add_paragraph(line)
    doc.save(str(path))
    return path


def make_pdf(path: Path, lines: list[str] = FAKE_RESUME_LINES) -> Path:
    """Minimal single-page text PDF written by hand (Helvetica, one line per row)."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    ops = ["BT", "/F1 10 Tf", "50 800 Td", "14 TL"]
    for ln in lines:
        ops.append(f"({esc(ln)}) Tj T*")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path
