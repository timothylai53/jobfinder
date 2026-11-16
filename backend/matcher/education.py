"""My education, as the matcher sees it: the highest level across every education entry.

Entries come from Experience Bank items (education / certification) and the Profile. An entry
that is still in progress counts at its level but earns half points and never triggers the gate.
"""
import re
from dataclasses import dataclass
from datetime import date

from matcher.rules import _EDU_PATTERNS, EDU_LEVELS

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
ONGOING = ("present", "current", "now", "ongoing", "expected", "in progress", "till date", "to date")
_EXPECTED = re.compile(
    rf"\b(?:expected|graduat\w*|completion|complete by|ending)\b[^.\n]{{0,25}}?({_MONTH}\s*\d{{4}}|\b20\d{{2}}\b)",
    re.IGNORECASE)
_IN_PROGRESS_TEXT = re.compile(r"\b(expected|in progress|ongoing|currently (?:pursuing|studying|enrolled)|final[- ]year|year \d of \d)\b",
                               re.IGNORECASE)
FIELD_ABBREVIATIONS = {
    "it": "Information Technology", "ict": "Information and Communication Technology",
    "cs": "Computer Science", "se": "Software Engineering", "is": "Information Systems",
}
_STOP = r"(?:\s*[,|–—(]|\s+-\s+|\s+(?:at|from|with|majoring)\b|$)"


@dataclass
class EduEntry:
    level: str
    field: str = ""
    in_progress: bool = False
    expected: str = ""  # YYYY-MM-DD when known
    source: str = ""  # "B3" or "profile"

    @property
    def rank(self) -> int:
        return EDU_LEVELS.get(self.level, 0)


def level_in(text: str) -> str | None:
    """Highest education level named in a resume line ("Master's degree" is Master, not Degree)."""
    text = re.sub(r"\b(master'?s?|doctoral|doctorate)\s+degree", r"\1", text, flags=re.IGNORECASE)
    found = [lvl for lvl, pat in _EDU_PATTERNS if pat.search(text)]
    return max(found, key=lambda l: EDU_LEVELS[l]) if found else None


def _clean_field(f: str) -> str:
    f = re.sub(r"\((?:hons?\.?|honours)\)", "", f, flags=re.IGNORECASE)
    f = re.sub(r"\b(?:with\s+)?(?:hons?\.?|honours)\b", "", f, flags=re.IGNORECASE)
    f = re.sub(r"\s+", " ", f).strip(" .,-/")
    return FIELD_ABBREVIATIONS.get(f.lower(), f)


def field_in(title: str) -> str:
    """Field of study from a qualification line.

    "Bachelor of IT (Hons) Software Engineering" -> "Software Engineering" (the specialisation wins),
    "Bachelor of Science in Computer Science"    -> "Computer Science",
    "Diploma in Information Technology, Politeknik X" -> "Information Technology".
    """
    t = title.strip()
    m = re.search(r"\((?:hons?\.?|honours)\)\s*(?:in\s+)?([A-Za-z][A-Za-z&/ ]{2,60}?)" + _STOP, t, re.IGNORECASE)
    if m and _clean_field(m.group(1)):
        return _clean_field(m.group(1))
    for prep in ("in", "of"):  # "of Science in Computer Science": the "in" part is the field
        ms = list(re.finditer(rf"\b{prep}\s+([A-Za-z][A-Za-z&/() ]{{1,60}}?)" + _STOP, t, re.IGNORECASE))
        if ms:
            f = _clean_field(ms[-1].group(1))
            if f and f.lower() not in ("science", "arts", "engineering", "technology", "the"):
                return f
    return ""


def _to_iso(s: str) -> str:
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s*(\d{4})", s)
    if m and m.group(1).lower() in _MONTHS:
        return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]:02d}-01"
    y = re.search(r"(20\d{2}|19\d{2})", s)
    return f"{y.group(1)}-06-01" if y else ""


def progress(end: str, text: str, today: date | None = None) -> tuple[bool, str]:
    """(in progress?, expected graduation YYYY-MM-DD) from an end date and the item's text."""
    today = today or date.today()
    e = end.strip().lower()
    expected = ""
    m = _EXPECTED.search(text)
    if m:
        expected = _to_iso(m.group(1))
    ongoing = any(e.startswith(w) for w in ONGOING) or bool(_IN_PROGRESS_TEXT.search(text))
    if not ongoing and e:
        iso = _to_iso(end)
        if iso and iso[:7] > today.strftime("%Y-%m"):  # an end date in the future
            ongoing, expected = True, expected or iso
    if expected and expected[:7] > today.strftime("%Y-%m"):
        ongoing = True
    return ongoing, expected if ongoing else ""


def from_item(code: str, title: str, organization: str, end: str, bullets: list[str],
              today: date | None = None) -> EduEntry | None:
    text = " ".join([title, organization])
    lvl = level_in(text)
    if not lvl:
        return None
    ongoing, expected = progress(end, " ".join([title, organization, *bullets]), today)
    return EduEntry(lvl, major_in([title, *bullets]) or field_in(title), ongoing, expected, code)


_MAJOR = re.compile(r"\b(?:major(?:ing)?(?:\s+in)?|specialisation|specialization|concentration)\s*[:\-]?\s*"
                    r"([A-Za-z][A-Za-z&/ ]{2,60}?)\s*(?:[,.;|(]|$)", re.IGNORECASE)
_HONOURS_PAREN = re.compile(r"\b(?:hons?\.?|honours|honors)\)?\s*\(([A-Za-z][A-Za-z&/ ]{2,60})\)", re.IGNORECASE)


def major_in(lines: list[str]) -> str:
    """'Major: Software Engineering' beats the degree name; 'with Honours (Information Technology)' is next best."""
    for ln in lines:
        m = _MAJOR.search(ln)
        if m:
            return _clean_field(m.group(1))
    for ln in lines:
        m = _HONOURS_PAREN.search(ln)
        if m:
            return _clean_field(m.group(1))
    return ""


def best(entries: list[EduEntry]) -> EduEntry | None:
    """Highest level wins; at the same level a completed entry beats an in-progress one."""
    entries = [e for e in entries if e and e.rank]
    if not entries:
        return None
    top = max(entries, key=lambda e: (e.rank, not e.in_progress, bool(e.field)))
    if not top.field:  # borrow a field from another entry at the same level
        top.field = next((e.field for e in entries if e.rank == top.rank and e.field), "")
    return top
