"""Heuristic resume text -> draft profile + Experience Bank items. Always reviewed by me before saving."""
import re
from dataclasses import asdict, dataclass, field

from matcher import education
from matcher.rules import normalize_language
from resume_parser.items import full_width, is_tech_line, join_wrapped, parse_items, skills_in  # noqa: F401
from resume_parser.patterns import (
    BULLET,
    CONTACT_LABEL,
    DATE_RANGE,
    EMAIL,
    ENGLISH_TESTS,
    PHONE,
    URL,
    DraftItem,
    heading_kind,
)
from skills.matcher import SkillMatcher

ITEM_KINDS = ("work", "project", "education", "certification", "achievement", "activity", "publication")


@dataclass
class DraftProfile:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    education_level: str = ""
    education_field: str = ""
    degree_status: str = "completed"
    expected_graduation: str = ""  # YYYY-MM-DD when found
    languages: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


def _split_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = [("header", [])]
    for ln in lines:
        kind = heading_kind(ln)
        if kind:
            # "Technical Skills" right under "SKILLS" is a sub-heading, not a new section
            if not (sections[-1][0] == kind and not sections[-1][1]):
                sections.append((kind, []))
        else:
            sections[-1][1].append(ln)
    return sections


def _education_profile(prof: DraftProfile, edu_items: list[DraftItem]) -> None:
    """Highest qualification across all education items (in-progress ones included)."""
    entries = [education.from_item("", it.title, it.organization, it.end, it.bullets) for it in edu_items]
    top = education.best([e for e in entries if e])
    if top is None:
        return
    prof.education_level = top.level
    prof.education_field = top.field
    prof.degree_status = "in_progress" if top.in_progress else "completed"
    prof.expected_graduation = top.expected


def strip_references(text: str) -> tuple[str, bool]:
    """Remove a References / Referees section (its heading up to the next known heading)."""
    out, skipping, found = [], False, False
    for ln in text.splitlines():
        kind = heading_kind(ln) if ln.strip() else None
        if kind == "references":
            skipping, found = True, True
            continue
        if kind and skipping:
            skipping = False
        if not skipping:
            out.append(ln)
    return "\n".join(out), found


def parse_resume_text(text: str, matcher: SkillMatcher) -> dict:
    text, had_references = strip_references(text)
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    width = full_width(lines)
    prof = DraftProfile()
    m = EMAIL.search(text)
    prof.email = m.group() if m else ""
    m = PHONE.search(text)
    prof.phone = m.group().strip() if m else ""
    for ln in lines[:5]:
        if not EMAIL.search(ln) and not PHONE.search(ln) and not heading_kind(ln) and 1 <= len(ln.split()) <= 5 \
                and not re.search(r"\d|@|http|:", ln):
            prof.name = ln.strip()
            break
    loc = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*),\s*(Malaysia|Selangor|Johor|Penang|Perak|Sabah|Sarawak|Kedah|"
                    r"Melaka|Pahang|Kelantan|Terengganu|Negeri Sembilan|Perlis|Putrajaya)\b", "\n".join(lines[:8]))
    prof.location = loc.group(0) if loc else ""

    items: list[DraftItem] = []
    sections = _split_sections(lines)
    for kind, sec_lines in sections:
        if kind in ITEM_KINDS:
            items.extend(parse_items(kind, sec_lines, matcher, width))
        elif kind == "skills":
            # "Languages: Java, …" / "Frameworks & Libraries: …" sub-lines all go to profile skills
            found = skills_in("\n".join(join_wrapped(sec_lines, width)), matcher)
            prof.skills += [s for s in found if s not in prof.skills]
        elif kind == "languages":
            for part in re.split(r"[,\n|•/;]", "\n".join(sec_lines)):
                lang = normalize_language(BULLET.sub("", part).strip()) if part.strip() else None
                if lang and lang not in prof.languages:
                    prof.languages.append(lang)
    _education_profile(prof, [i for i in items if i.type in ("education", "certification")])
    if any(ENGLISH_TESTS.search(i.title) for i in items) and "English" not in prof.languages:
        prof.languages.append("English")  # MUET / IELTS / TOEFL imply English
    return {"profile": asdict(prof), "items": [asdict(i) for i in items],
            "unparsed_lines": _unparsed_lines(sections, prof, items, matcher),
            "raw_text": text, "skipped_sections": ["references"] if had_references else []}


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _unparsed_lines(sections, prof: DraftProfile, items: list[DraftItem], matcher: SkillMatcher) -> list[dict]:
    """Lines of the resume that did not end up in any draft field, so I can check them by hand."""
    words = set(" ".join(_squash(x) for x in [
        prof.name, prof.email, prof.phone, prof.location,
        *[f for it in items for f in (it.title, it.organization, it.start, it.end, *it.bullets, *it.skills)],
    ] if x).split())
    out = []
    for kind, sec_lines in sections:
        for ln in sec_lines:
            text = BULLET.sub("", ln).strip()
            core = _squash(DATE_RANGE.sub(" ", text))
            if not core:
                continue
            if kind == "skills" and matcher.find(text):
                continue
            if kind in ITEM_KINDS and is_tech_line(text, matcher):
                continue  # tech-stack line: went into the item's skills
            if kind == "languages" and normalize_language(text):
                continue
            if kind == "header" and (EMAIL.search(text) or PHONE.search(text) or URL.search(text) or CONTACT_LABEL.match(text)):
                continue  # contact lines (address, LinkedIn, GitHub labels): not part of the bank
            if all(w in words for w in core.split()):
                continue
            reason = {"summary": "summary is not imported", "header": "not recognised"}.get(
                kind, f"not placed in any {kind} field" if kind not in ("skills", "languages", "contact")
                else f"no known {kind} found")
            out.append({"line": text, "section": kind, "reason": reason})
    return out
