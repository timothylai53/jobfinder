"""Shared resume patterns: section headings, bullets, dates, contacts, header separators."""
import re
from dataclasses import dataclass, field

SECTION_HEADINGS = {
    "work": ("experience", "work experience", "professional experience", "employment", "employment history",
             "work history", "internship", "internships", "internship experience", "working experience",
             "relevant experience"),
    "project": ("projects", "project", "personal projects", "academic projects", "selected projects",
                "project experience", "side projects"),
    "education": ("education", "academic background", "education background", "academic qualifications",
                  "qualifications", "educational background"),
    "certification": ("certifications", "certification", "certificates", "licenses & certifications",
                      "licenses and certifications", "courses", "training"),
    "achievement": ("achievements", "achievement", "awards", "award", "honors", "honours", "awards & achievements",
                    "awards and achievements", "honours and awards", "honors and awards"),
    # Activities become achievement items, one per block (a short sub-heading like "University Level" groups them).
    "activity": ("activities", "extracurricular activities", "extra-curricular activities", "co-curricular activities",
                 "cocurricular activities", "leadership", "volunteering", "volunteer experience"),
    "publication": ("publications", "publication", "research & publications", "research and publications",
                    "research", "papers", "conference papers"),
    "skills": ("skills", "technical skills", "core skills", "key skills", "skills & tools", "tools",
               "technologies", "skills and tools"),
    "languages": ("languages", "language", "language proficiency"),
    "summary": ("summary", "profile", "about me", "objective", "career objective", "professional summary"),
    "contact": ("contact", "contact information", "personal details", "personal information"),
    # Never imported: referee names and contact details stay out of the bank (and out of stored text).
    "references": ("references", "reference", "referees", "referee", "references available upon request",
                   "reference available upon request"),
}
_HEADING_LOOKUP = {h: kind for kind, names in SECTION_HEADINGS.items() for h in names}

BULLET = re.compile(r"^\s*([\-\*•▪●○◦–‣⁃➢►]|\d{1,2}[.)])\s*")
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:{MONTH}\s*\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}}-\d{{2}}|\d{{4}})"
DATE_RANGE = re.compile(
    rf"({_DATE})\s*(?:-|–|—|to|until)\s*({_DATE}|present|current|now|ongoing|today)", re.IGNORECASE)
SINGLE_DATE = re.compile(rf"(?:expected\s+|graduat\w*\s+)?({MONTH}\s*\d{{4}}|\b(?:19|20)\d{{2}}\b)", re.IGNORECASE)
YEAR_ONLY = re.compile(rf"^\(?({MONTH}\s*)?(19|20)\d{{2}}\)?$", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?6?0)[\s-]?1\d[\s-]?\d{3,4}[\s-]?\d{3,4}|\+?\d[\d\s-]{8,14}\d")
CONTACT_LABEL = re.compile(r"^(address|email|e-mail|phone|mobile|tel|linkedin|github|portfolio|website)\s*:?", re.IGNORECASE)
URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Title / organization separators in a header line ("Admin Clerk (Full Time) - Kedai Contoh, Kuantan").
SPLIT_HEADER = re.compile(r"\s+(?:\||@|–|—|-|·|•|,|at)\s+")
SPACED_SEP = re.compile(r"\s(?:-|–|—|·|•|\|)\s")
# Language tests and certificates become their own certification items wherever they appear.
CERT_LINE = re.compile(
    r"\b(MUET|IELTS|TOEFL|TOEIC|PTE Academic|Cambridge English|Linguaskill|JLPT|HSK|TOPIK|DELF|Goethe|"
    r"certified|certificate|certification)\b", re.IGNORECASE)
ENGLISH_TESTS = re.compile(r"\b(MUET|IELTS|TOEFL|TOEIC|PTE Academic|Cambridge English|Linguaskill)\b", re.IGNORECASE)
STRIP = " |,-–—·•()"


def heading_kind(line: str) -> str | None:
    s = BULLET.sub("", line).strip().rstrip(":").strip()
    if not s or len(s) > 40:
        return None
    return _HEADING_LOOKUP.get(re.sub(r"\s+", " ", s.lower()))


def norm_date(s: str) -> str:
    return s.strip().rstrip(".").title() if not s.strip().isdigit() else s.strip()


@dataclass
class DraftItem:
    type: str
    title: str = ""
    organization: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
