"""Lines of one resume section -> draft Experience Bank items.

Rule of thumb: a NEW item starts only on a header line. A header line has a date range, or a spaced
" - " / " · " / " | " title-organization separator, or is a short title followed by a tech-stack line
(projects) or by bullets/dates. Everything else is prose: it is joined to the current item's last
bullet while that bullet hasn't ended its sentence, otherwise it becomes the next bullet.
"""
import re

from matcher import education
from resume_parser.patterns import (
    BULLET, CERT_LINE, DATE_RANGE, SINGLE_DATE, SPACED_SEP, SPLIT_HEADER, STRIP, YEAR_ONLY, DraftItem,
    heading_kind, norm_date,
)
from skills.matcher import SkillMatcher

FUNCTION_WORDS = {"and", "or", "of", "the", "with", "using", "for", "to", "in", "on", "at", "by", "a", "an", "as",
                  "from", "including", "via", "into", "while", "such", "&", "plus"}
_GPA = re.compile(r"\s+((?:C?GPA|GCPA|CGPA)\s*:?\s*\d.*)$", re.IGNORECASE)
_SENTENCE_END = (".", "!", "?")
_LABEL = re.compile(r"^[A-Z][\w &/]{1,30}\s*:\s*\S")  # "Major: Software Engineering", "GPA: 3.8"
_SUBHEADING = re.compile(r"^[A-Z][A-Za-z&]*(?:\s[A-Z][A-Za-z&]*){0,2}$")  # 1-3 capitalised words, e.g. "University Level"


def full_width(lines: list[str]) -> int:
    """Typical width of a full line in this document (95th percentile, links ignored)."""
    lens = sorted(len(l.strip()) for l in lines if l.strip() and "http" not in l)
    return lens[int(len(lens) * 0.95)] if lens else 0


def skills_in(text: str, matcher: SkillMatcher) -> list[str]:
    """Skills mentioned, without overlaps ("Tailwind CSS" is not also "CSS")."""
    return list(dict.fromkeys(name for _, _, name in matcher.find_spans(text)))


def _tech_parts(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,;|·•]", text) if p.strip()]


def is_tech_line(text: str, matcher: SkillMatcher) -> bool:
    """'Vue.js, Node.js, MongoDB, RESTful API, DigitalOcean': a list made mostly of known skills."""
    if not text or text.endswith(".") or len(text.split()) > 20 or BULLET.match(text) or text[:1].islower():
        return False
    parts = _tech_parts(text)
    if len(parts) < 2 or any(len(p.split()) > 4 for p in parts):
        return False
    hits = sum(1 for p in parts if skills_in(p, matcher))
    return hits >= 2 and hits / len(parts) >= 0.5


def tech_skills(text: str, matcher: SkillMatcher) -> list[str]:
    """Known skills by canonical name; unknown parts (DigitalOcean, SendGrid API) kept as written."""
    out: list[str] = []
    for p in _tech_parts(text):
        found = skills_in(p, matcher)
        out += found if found else [p]
    return list(dict.fromkeys(out))


def join_wrapped(lines: list[str], width: int = 0, matcher: SkillMatcher | None = None) -> list[str]:
    """Undo line wraps. A line joins the previous one when the previous one
    - has an unclosed bracket, or ends with a hyphen ("Part-" + "Time)"), a comma, "&" or a word like "and/using/on";
    - does not end a sentence and this line starts in lowercase;
    - is nearly full width (85% of the typical line) and does not end a sentence.
    Never across bullets, headings, date lines or tech-stack lines.
    """
    out: list[str] = []
    prev_physical = 0  # length of the previous source line (before joining)
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        physical, prev_physical = prev_physical, len(s)
        labelled = bool(_LABEL.match(s))  # "Major: Software Engineering" is a deliberate new line, not a wrap
        if out and not BULLET.match(ln) and not heading_kind(s) and not DATE_RANGE.search(s) and not labelled \
                and not DATE_RANGE.search(out[-1]) and not (matcher and (is_tech_line(s, matcher) or is_tech_line(out[-1], matcher))):
            prev = out[-1].rstrip()
            words = prev.split()
            last = words[-1].lower() if words else ""
            unclosed = prev.count("(") > prev.count(")")
            hyphen = prev.endswith("-") and not prev.endswith(" -")
            ends_sentence = prev.endswith(_SENTENCE_END + (":",))
            lower_cont = s[:1].islower() and not ends_sentence
            dangling = prev.endswith((",", "&")) or last in FUNCTION_WORDS
            full = bool(width) and physical >= 0.85 * width and not ends_sentence and not prev.endswith(")")
            if unclosed or hyphen or s.startswith(")") or lower_cont or dangling or full:
                glue = "" if hyphen or s.startswith(")") else " "
                out[-1] = prev + glue + s
                continue
        out.append(ln.rstrip())
    return out


def _is_sentence(text: str) -> bool:
    return text.endswith(_SENTENCE_END) or len(text.split()) > 14


def _titleish(text: str) -> bool:
    words = text.split()
    caps = sum(1 for w in words if w[:1].isupper() or not w[:1].isalpha())
    return 1 <= len(words) <= 9 and not text.endswith(_SENTENCE_END) and caps / len(words) >= 0.6 and ":" not in text


def _split_dates(text: str) -> tuple[str, str, str]:
    """('Network Technician (Intern) - Contoh Sdn Bhd', 'Apr 2022', 'Aug 2022') from a header with dates at the end."""
    dr = DATE_RANGE.search(text)
    if not dr:
        return text, "", ""
    rest = (text[: dr.start()] + " " + text[dr.end():]).strip(" |,-–—·•")
    return re.sub(r"\s+", " ", rest), norm_date(dr.group(1)), norm_date(dr.group(2))


def _dates_only(text: str) -> bool:
    rest, start, _ = _split_dates(text)
    return bool(start) and not rest


def _fill_header(item: DraftItem, text: str) -> None:
    rest, start, end = _split_dates(text)
    if start and not item.start:
        item.start, item.end = start, end
    elif not item.start and not item.end and item.type in ("education", "certification", "achievement"):
        sd = SINGLE_DATE.search(rest)
        if sd and len(rest) < 80 and not education.level_in(sd.group(0)):
            item.end = norm_date(sd.group(1))
            rest = (rest[: sd.start()] + rest[sd.end():]).strip(STRIP)
    if not rest:
        return
    if item.type == "education" and not item.title and not education.level_in(rest):
        # Institution-first layout: "Universiti Contoh (UCM) - Perlis  Sep 2023 - Present", qualification on the next line.
        item.organization = SPACED_SEP.sub(", ", rest)
        return
    if not item.title:
        title, _, gpa = _split_gpa(rest)
        parts = [p.strip() for p in SPLIT_HEADER.split(title, maxsplit=1) if p.strip()]
        item.title = parts[0] if parts else title
        if len(parts) > 1 and not item.organization:
            item.organization = parts[1]
        if gpa:
            item.bullets.append(gpa)
    elif not item.organization:
        item.organization = rest
    else:
        item.bullets.append(rest)


def _split_gpa(text: str) -> tuple[str, str, str]:
    m = _GPA.search(text)
    return (text[: m.start()].strip(), "", m.group(1).strip()) if m else (text, "", "")


def _add_prose(item: DraftItem, text: str) -> None:
    """Continue the last bullet while it hasn't ended its sentence; otherwise start a new bullet."""
    # "Major: Software Engineering" / "GPA: 3.8" lines stand on their own
    if item.bullets and not item.bullets[-1].rstrip().endswith(_SENTENCE_END) and not BULLET.match(text) \
            and not _LABEL.match(text) and not _LABEL.match(item.bullets[-1]):
        item.bullets[-1] = item.bullets[-1].rstrip() + " " + text
    else:
        item.bullets.append(text)


# ---------- per-kind parsers ----------

def parse_items(kind: str, lines: list[str], matcher: SkillMatcher, width: int = 0) -> list[DraftItem]:
    logical = join_wrapped(lines, width, matcher)
    if kind == "publication":
        return _publication(logical)
    if kind in ("achievement", "certification"):
        return _one_per_line(kind, logical, matcher)
    if kind == "activity":
        return _activities(logical, matcher)
    return _entries(kind, logical, matcher)


def _cert_item(text: str) -> DraftItem:
    cert = DraftItem(type="certification")
    _fill_header(cert, text)
    return cert


def _entries(kind: str, logical: list[str], matcher: SkillMatcher) -> list[DraftItem]:
    items: list[DraftItem] = []
    cur: DraftItem | None = None
    for i, ln in enumerate(logical):
        is_bullet = bool(BULLET.match(ln)) and not DATE_RANGE.search(ln[:6])
        text = BULLET.sub("", ln).strip() if is_bullet else ln.strip()
        if not text:
            continue
        nxt = logical[i + 1] if i + 1 < len(logical) else ""
        nxt_text = BULLET.sub("", nxt).strip()

        if CERT_LINE.search(text) and not _is_sentence(text):
            items.append(_cert_item(text))
            continue
        if cur is not None and is_tech_line(text, matcher):
            cur.skills += [s for s in tech_skills(text, matcher) if s not in cur.skills]
            continue
        if is_bullet:
            if cur is None:
                cur = DraftItem(type=kind)
                items.append(cur)
            cur.bullets.append(text)
            continue

        rest, start, _ = _split_dates(text)
        if start and not rest:  # a line with only dates
            if cur is not None and not cur.start:
                _fill_header(cur, text)
            else:
                cur = DraftItem(type=kind)
                items.append(cur)
                _fill_header(cur, text)
            continue
        if YEAR_ONLY.match(text) and cur is not None and not cur.end:
            cur.end = norm_date(text.strip("()"))
            continue

        level = education.level_in(text) if kind == "education" else None
        if kind == "education" and cur is not None and not cur.title and level and not start:
            _fill_header(cur, text)  # qualification under an institution header
            continue
        header = bool(start) \
            or (bool(SPACED_SEP.search(text)) and not _is_sentence(text) and len(text.split()) <= 16) \
            or is_tech_line(nxt_text, matcher) \
            or (_titleish(text) and bool(nxt) and (bool(BULLET.match(nxt)) or _dates_only(nxt_text))) \
            or (kind == "education" and cur is not None and bool(level) and bool(education.level_in(cur.title)))
        if cur is None or header:
            cur = DraftItem(type=kind)
            items.append(cur)
            _fill_header(cur, text)
        elif not cur.title and not cur.bullets:
            _fill_header(cur, text)
        else:
            _add_prose(cur, text)
    return _finish(items, matcher)


def _year(text: str) -> str:
    years = re.findall(r"(?:19|20)\d{2}", text)
    return years[-1] if years else ""


def _title_and_detail(text: str) -> tuple[str, str]:
    """'Participant, X Hackathon 2025: Showcased …' / 'High Academic Achiever (Diploma) Consistently …'."""
    t = text.strip().rstrip(".")
    m = re.match(r"^([^:]{6,90}):\s+(.+)$", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m = re.match(r"^(.{6,80}?\))\s+([A-Z].{10,})$", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return t, ""


def _one_per_line(kind: str, logical: list[str], matcher: SkillMatcher) -> list[DraftItem]:
    """Achievements / certifications: each (joined) line is one item."""
    items: list[DraftItem] = []
    for ln in logical:
        text = BULLET.sub("", ln).strip()
        if not text:
            continue
        if items and (text.startswith("(") or text[:1].islower()):
            items[-1].bullets.append(text)
            continue
        if kind == "certification" or (CERT_LINE.search(text) and len(text) < 80):
            items.append(_cert_item(text))
            continue
        title, detail = _title_and_detail(text)
        item = DraftItem(type="achievement", title=title, end=_year(text))
        if detail:
            item.bullets.append(detail)
        items.append(item)
    return _finish(items, matcher)


def _activities(logical: list[str], matcher: SkillMatcher) -> list[DraftItem]:
    """Extracurricular: a short sub-heading ("University Level") groups the activities below it."""
    items: list[DraftItem] = []
    group = ""
    for i, ln in enumerate(logical):
        text = BULLET.sub("", ln).strip()
        if not text:
            continue
        if _SUBHEADING.match(text) and i + 1 < len(logical):
            group = text
            continue
        if items and (text.startswith("(") or text[:1].islower() or BULLET.match(ln)):
            items[-1].bullets.append(text)
            continue
        rest, start, end = _split_dates(text)
        title, detail = _title_and_detail(rest)
        item = DraftItem(type="achievement", title=title, organization=group, start=start, end=end or _year(text))
        if detail:
            item.bullets.append(detail)
        items.append(item)
    return _finish(items, matcher)


def _publication(logical: list[str]) -> list[DraftItem]:
    """The whole section is one citation: title, venue and year are picked out, the full text kept as a bullet."""
    text = " ".join(BULLET.sub("", ln).strip() for ln in logical if ln.strip())
    if not text:
        return []
    title = re.search(r"\)\.\s*(.+?)\.(?:\s|$)", text)
    venue = re.search(r"presented at (?:the )?(.+?)(?:,|\.(?:\s|$))", text, re.IGNORECASE)
    item = DraftItem(type="publication", title=title.group(1).strip() if title else text[:120],
                     organization=venue.group(1).strip() if venue else "", end=_year(text[:40]) or _year(text),
                     bullets=[text])
    return [item]


def _finish(items: list[DraftItem], matcher: SkillMatcher) -> list[DraftItem]:
    for it in items:
        found = skills_in("\n".join([it.title, it.organization, *it.bullets]), matcher)
        it.skills = list(dict.fromkeys([*it.skills, *found]))
    return [it for it in items if it.title or it.bullets]
