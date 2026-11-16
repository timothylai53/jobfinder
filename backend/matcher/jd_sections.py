"""Split a job description into clauses and label each as required / preferred / ignored.

Priority for a clause: preferred phrase or preferred section > required phrase > section > default (required).
Responsibilities / duties sections count as preferred (they describe the job, not hard requirements).
Sections that clearly describe the company or perks (About us, Benefits, ...) are ignored.
"""
import re
from dataclasses import dataclass

REQUIRED_HEADINGS = (
    "requirements", "requirement", "job requirements", "qualifications", "qualification",
    "minimum qualifications", "basic qualifications", "must have", "must-have", "must haves",
    "what you need", "what you'll need", "what you will need", "what we are looking for",
    "what we're looking for", "who you are", "who we are looking for", "you have", "you should have",
    "what you bring", "skills", "skills and experience", "required skills", "technical skills",
    "key skills", "candidate requirements", "job specification", "experience", "competencies",
    "the role", "job description", "about the role", "about the job", "about you", "about the position", "job summary",
    "education", "education requirements", "academic qualification", "academic qualifications",
)
# Duties describe the job, not hard requirements: skills found there count as preferred.
RESPONSIBILITY_HEADINGS = (
    "responsibilities", "job responsibilities", "key responsibilities", "your responsibilities",
    "roles and responsibilities", "role and responsibilities", "roles & responsibilities",
    "duties", "duties and responsibilities", "job duties", "key duties", "what you will do",
    "what you'll do", "what you'll be doing", "what you will be doing", "your role", "scope of work",
    "day to day", "a day in the life",
)
PREFERRED_HEADINGS = (
    "preferred", "preferred qualifications", "preferred skills", "nice to have", "nice-to-have",
    "nice to haves", "good to have", "bonus", "bonus points", "bonus if you have", "a plus",
    "pluses", "desirable", "advantages", "added advantage", "it would be great if",
)
IGNORED_HEADINGS = (
    "about us", "about the company", "who we are", "company overview", "company description",
    "benefits", "perks", "what we offer", "why join us", "why us", "we offer", "perks and benefits",
    "how to apply", "salary", "compensation", "working hours", "equal opportunity",
    "additional information", "about", "our culture", "life at",
)

PREFERRED_PHRASES = re.compile(
    r"\b(nice[\s-]to[\s-]have|good[\s-]to[\s-]have|is an? (added )?advantage|added advantage|"
    r"advantageous|an advantage|is a plus|a plus|preferred|preferably|preferable|bonus|desirable|"
    r"would be great|is beneficial|beneficial|ideally|optional)\b",
    re.IGNORECASE,
)
REQUIRED_PHRASES = re.compile(
    r"\b(required|requirement|must|mandatory|essential|compulsory|minimum|at least|necessary)\b",
    re.IGNORECASE,
)

_BULLET = re.compile(r"^\s*([\-\*•▪●○◦–‣⁃>]|\d{1,2}[.)])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[.;!?])\s+(?=[A-Z])|;\s*")


@dataclass
class Clause:
    text: str
    kind: str  # required / preferred / ignored
    section: str  # normalized heading text, "" when none


def _norm_heading(text: str) -> str:
    t = _BULLET.sub("", text).strip().strip(":").strip()
    t = re.sub(r"[^\w\s'&-]", "", t).strip().lower()
    return re.sub(r"\s+", " ", t)


def _heading_kind(h: str) -> str | None:
    if not h:
        return None
    for kind, names in (("preferred", PREFERRED_HEADINGS), ("preferred", RESPONSIBILITY_HEADINGS),
                        ("required", REQUIRED_HEADINGS), ("ignored", IGNORED_HEADINGS)):
        if h in names:
            return kind
    if h.startswith(("preferred", "nice to have", "bonus", "good to have", "responsibilit", "duties")):
        return "preferred"
    if h.startswith(("requirement", "qualification", "must have", "minimum qualification")):
        return "required"
    if h.startswith(("about ", "why join", "benefits", "perks", "what we offer")):
        return "ignored"
    return None


# Headings that really list requirements. Generic ones ("Job description", "The role", "About the job") are
# REQUIRED_HEADINGS for clause defaults, but don't count as a requirements section (decision #113).
_GENERIC_HEADINGS = ("the role", "job description", "about the role", "about the job", "about the position", "job summary")


def is_requirements_section(section: str) -> bool:
    return bool(section) and section not in _GENERIC_HEADINGS and _heading_kind(section) == "required"


def section_type(section: str) -> str | None:
    """"required" / "responsibility" / "preferred" (nice to have) / "ignored" / None for a clause's section."""
    if not section:
        return None
    if section in RESPONSIBILITY_HEADINGS or section.startswith(("responsibilit", "duties")):
        return "responsibility"
    return _heading_kind(section)


def _is_heading_line(line: str) -> bool:
    s = line.strip()
    if not s or _BULLET.match(s) or len(s) > 60:
        return False
    if s.endswith(":"):
        return True
    words = s.split()
    return len(words) <= 6 and (s.isupper() or _heading_kind(_norm_heading(s)) is not None) and not s.endswith(".")


def classify_clause(text: str, section_kind: str | None) -> str:
    if PREFERRED_PHRASES.search(text) or section_kind == "preferred":
        return "preferred"
    if REQUIRED_PHRASES.search(text):
        return "required"
    return section_kind or "required"


def split_clauses(jd: str) -> list[Clause]:
    clauses: list[Clause] = []
    section, section_kind = "", None
    for raw in jd.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Inline heading: "Requirements: Python, SQL"
        m = re.match(r"^([A-Za-z][A-Za-z '&/-]{2,40}):\s*(.+)$", _BULLET.sub("", line))
        if m and _heading_kind(_norm_heading(m.group(1))):
            section = _norm_heading(m.group(1))
            section_kind = _heading_kind(section)
            line = m.group(2)
        elif _is_heading_line(line):
            h = _norm_heading(line)
            kind = _heading_kind(h)
            # Unknown all-caps headings (e.g. a company tagline) keep the default.
            section, section_kind = h, kind
            continue
        body = _BULLET.sub("", line)
        for part in _CLAUSE_SPLIT.split(body):
            part = part.strip()
            if not part:
                continue
            kind = "ignored" if section_kind == "ignored" else classify_clause(part, section_kind)
            clauses.append(Clause(text=part, kind=kind, section=section))
    return clauses
