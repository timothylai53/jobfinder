"""Fabrication guard (brief §6.6 point 3): flag, never silently fix.

- any bullet whose source_id is missing or not in the Experience Bank;
- any ID (evidence / used / suggested / omitted) that isn't in the bank;
- any skill that is not in my bank or profile (skills_order, and dictionary skills named in rewritten text);
- tailor_resume / cover_letter: any number, percentage, count or money amount that isn't in the source bank item
  (bullets) or anywhere in my bank/profile (summary, cover-letter paragraphs) -> "new_number" (red);
- tailor_resume bullets: a dictionary skill I do have, but not in THAT bank item -> "skill_not_in_item" (amber);
- parse_resume: titles, organizations and skills that don't appear in the resume text it was given.

Each flag: {"path": "sections.0.items.2", "kind": "unknown_id" | "missing_id" | "unknown_skill" | "not_in_source" |
"new_number" | "skill_not_in_item", "message": "..."} so the review screen can show it in red next to the right item.
"""
import re
from dataclasses import dataclass, field

from skills.matcher import SkillMatcher


@dataclass
class Facts:
    """What I really have: bank item codes and the skills shown by my bank or profile."""
    codes: set[str]
    skills: set[str]  # canonical names
    matcher: SkillMatcher
    item_types: dict[str, str] = field(default_factory=dict)  # code -> type
    item_skills: dict[str, set[str]] = field(default_factory=dict)  # code -> canonical skills that item shows
    item_text: dict[str, str] = field(default_factory=dict)  # code -> title, organization, dates, bullets, skills
    profile_text: str = ""  # profile fields a summary may draw on (no email, phone or name)
    item_headers: dict[str, list[str]] = field(default_factory=dict)  # code -> [title, organization, start, end]

    @property
    def all_text(self) -> str:
        return "\n".join([*self.item_text.values(), self.profile_text])


def _flag(path: str, kind: str, message: str) -> dict:
    return {"path": path, "kind": kind, "message": message}


def _norm_code(code: str) -> str:
    return (code or "").strip().upper()


def _ids(flags: list, path: str, ids: list[str], facts: Facts, what: str) -> None:
    for i, code in enumerate(ids):
        if _norm_code(code) not in facts.codes:
            flags.append(_flag(f"{path}.{i}", "unknown_id", f"{what} {code!r} is not in your Experience Bank"))


def _skill_known(skill: str, facts: Facts) -> tuple[bool, str]:
    canon = facts.matcher.normalize_list([skill])
    name = canon[0] if canon else skill.strip()
    return (name in facts.skills), name


def _text_skills(flags: list, path: str, text: str, facts: Facts) -> None:
    """Dictionary skills named in generated text that I don't have."""
    for s in facts.matcher.find(text or ""):
        if s not in facts.skills:
            flags.append(_flag(path, "unknown_skill", f"mentions {s}, which is not in your bank or profile"))


# A number as written: optional currency, digits (1,000 / 2.5), optional k/m/million, then %, +, x or an ordinal.
# Digits glued to letters (HTML5, ES6, B12) are not numbers.
_NUM = re.compile(
    r"(?<![\w.])(?:(?:RM|MYR|USD|SGD|US\$|S\$|\$|€|£)\s?)?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<dec>\d+))?"
    r"(?P<mult>\s?(?:million|billion|mil|bil)|k|m|b)?"
    r"(?P<suf>\s?%|\s?percent|\+|x|×|st|nd|rd|th)?(?!\w)", re.I)
_MULT = {"k": 1e3, "m": 1e6, "mil": 1e6, "million": 1e6, "b": 1e9, "bil": 1e9, "billion": 1e9}


def numbers(text: str) -> list[tuple[str, tuple[float, str]]]:
    """(as written, comparable key). The key is the value plus whether it's a percentage or a multiple,
    so "RM 2k" matches "RM2,000" and "500+" matches "500", but "40%" doesn't match a plain 40."""
    out = []
    for m in _NUM.finditer(text or ""):
        value = float(m["int"].replace(",", "") + (f".{m['dec']}" if m["dec"] else ""))
        value *= _MULT.get((m["mult"] or "").strip().lower(), 1)
        suf = (m["suf"] or "").strip().lower()
        kind = "pct" if suf in ("%", "percent") else "times" if suf in ("x", "×") else "n"
        out.append((m.group(0).strip(), (round(value, 6), kind)))
    return out


def _new_numbers(flags: list, path: str, text: str, source: str, where: str) -> None:
    known = {k for _, k in numbers(source)}
    seen = set()
    for written, key in numbers(text):
        if key not in known and key not in seen:
            seen.add(key)
            flags.append(_flag(path, "new_number", f"{written!r} doesn't appear in {where}: check this number"))


_ITEM_WORD = {"project": "this project", "work": "this job", "education": "this course"}


def _item_skills(flags: list, path: str, text: str, code: str, facts: Facts) -> None:
    """Skills I have somewhere, but not in the bank item this bullet claims to come from."""
    mine = facts.item_skills.get(code, set())
    for s in facts.matcher.find(text or ""):
        if s in facts.skills and s not in mine:  # not in my bank at all is already flagged red
            what = _ITEM_WORD.get(facts.item_types.get(code, ""), "this item")
            flags.append(_flag(path, "skill_not_in_item", f"{s} isn't in {code}: is that true for {what}?"))


# ---------- tailor_resume: one bullet per item, no repeated header ----------

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE = rf"(?:(?:{_MONTH}\s+)?\d{{4}}|{_MONTH}|present|current|now|ongoing|today)"
_SEP = r"(?:[\s,|:;()•.\-–—]|\b(?:to|at|until)\b)*"
_STRONG_SEP = re.compile(r"[,|:;.\-–—]")


def strip_header(text: str, header: list[str]) -> tuple[str, str]:
    """Remove the bank item's title / organization / dates if the AI put them at the start of a bullet.

    Returns (bullet, removed prefix). Strips only when the prefix names at least two header parts
    ("Intern, Contoh Tech, Mar 2025 - Present. Redesigned ...") or one part plus a clear separator
    ("Intern: Redesigned ..."), so a bullet that merely starts with a word from the title is kept."""
    fields = sorted((re.escape(f.strip()) for f in header if f and f.strip()), key=len, reverse=True)
    alts = "|".join([*fields, _DATE]) if fields else _DATE
    part = re.compile(rf"(?:{alts})(?=[\s,|:;()•.\-–—]|$)", re.I)
    sep = re.compile(_SEP, re.I)
    pos, parts, named, last_sep = 0, 0, 0, ""
    while True:
        m = part.match(text, pos)
        if not m:
            break
        parts += 1
        named += not re.fullmatch(_DATE, m.group(0), re.I)
        pos = sep.match(text, m.end()).end()
        last_sep = text[m.end():pos]
    rest = text[pos:].strip()
    if not named or not rest:  # dates alone ("2024: built ...") are left as written
        return text, ""
    if parts < 2 and not _STRONG_SEP.search(last_sep):
        return text, ""
    return rest[0].upper() + rest[1:], text[:pos].strip(" ,|:;.-–—")


_ABBREV = {"e.g", "i.e", "etc", "vs", "sdn", "bhd", "inc", "ltd", "co", "dr", "mr", "ms", "no", "approx"}


def sentences(text: str) -> list[str]:
    """Split a merged paragraph into its sentences (one bullet each). Abbreviations like "e.g." don't split."""
    out, start = [], 0
    for m in re.finditer(r"[.!?;]\s+(?=[A-Z])", text):
        word = re.search(r"([\w.]+)$", text[start:m.start()])
        if m.group(0)[0] == "." and word and word.group(1).lower().rstrip(".") in _ABBREV:
            continue
        out.append(text[start:m.start() + 1].strip().rstrip(";"))
        start = m.end()
    out.append(text[start:].strip())
    return [s for s in out if s]


def tidy_tailor(data: dict, facts: Facts) -> list[dict]:
    """Strip a repeated title/organization/date prefix from each bullet (in place), and warn about it and about
    several bullets merged into one. Both are amber: the content is kept, only its shape is off."""
    flags: list[dict] = []
    for s, sec in enumerate(data.get("sections", [])):
        for j, item in enumerate(sec.get("items", [])):
            path, code = f"sections.{s}.items.{j}", _norm_code(item.get("source_id", ""))
            text = item.get("text", "")
            if code in facts.item_headers:
                text, removed = strip_header(text, facts.item_headers[code])
                if removed:
                    item["text"] = text
                    flags.append(_flag(path, "header_removed", f"Removed “{removed}” from the start: the resume "
                                                               f"already prints {code}'s title, organization and dates."))
            n = len(sentences(text))
            if n > 1:
                flags.append(_flag(path, "several_bullets", f"This looks like {n} bullets in one. "
                                                            "Split it so each prints as its own bullet."))
    return flags


def check(task: str, data: dict, facts: Facts, source_text: str = "") -> list[dict]:
    flags: list[dict] = []
    if task == "tailor_resume":
        for i, sk in enumerate(data.get("skills_order", [])):
            ok, name = _skill_known(sk, facts)
            if not ok:
                flags.append(_flag(f"skills_order.{i}", "unknown_skill", f"{name} is not in your bank or profile"))
        _text_skills(flags, "summary", data.get("summary", ""), facts)
        _new_numbers(flags, "summary", data.get("summary", ""), facts.all_text, "your bank or profile")
        for s, sec in enumerate(data.get("sections", [])):
            for j, item in enumerate(sec.get("items", [])):
                path = f"sections.{s}.items.{j}"
                sid = _norm_code(item.get("source_id", ""))
                if not sid:
                    flags.append(_flag(path, "missing_id", "no source_id: this bullet isn't tied to any bank item"))
                elif sid not in facts.codes:
                    flags.append(_flag(path, "unknown_id", f"source_id {item.get('source_id')!r} is not in your Experience Bank"))
                _text_skills(flags, path, item.get("text", ""), facts)
                if sid in facts.codes:  # a missing or unknown ID is already red; there's no source to compare with
                    _new_numbers(flags, path, item.get("text", ""), facts.item_text.get(sid, ""), sid)
                    _item_skills(flags, path, item.get("text", ""), sid, facts)
        _ids(flags, "omitted_ids", data.get("omitted_ids", []), facts, "omitted ID")
    elif task == "cover_letter":
        _ids(flags, "used_ids", data.get("used_ids", []), facts, "used ID")
        for i, p in enumerate(data.get("paragraphs", [])):
            _text_skills(flags, f"paragraphs.{i}", p, facts)
            _new_numbers(flags, f"paragraphs.{i}", p, facts.all_text, "your bank or profile")
    elif task == "deep_analysis":
        for i, r in enumerate(data.get("requirements", [])):
            _ids(flags, f"requirements.{i}.evidence_ids", r.get("evidence_ids", []), facts, "evidence ID")
            if r.get("status") in ("met", "partial") and not r.get("evidence_ids"):
                flags.append(_flag(f"requirements.{i}", "missing_id", f"marked {r.get('status')} without any evidence ID"))
    elif task == "interview_prep":
        for i, q in enumerate(data.get("questions", [])):
            _ids(flags, f"questions.{i}.suggested_points_ids", q.get("suggested_points_ids", []), facts, "suggested ID")
    elif task == "parse_resume":
        flags += _check_parsed_resume(data, source_text)
    return flags


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _check_parsed_resume(data: dict, source_text: str) -> list[dict]:
    """A parsed resume may only contain what the resume says."""
    flags: list[dict] = []
    text = f" {_squash(source_text)} "
    if not text.strip():
        return flags

    def present(value: str) -> bool:
        v = _squash(value)
        return not v or f" {v} " in text

    for i, it in enumerate(data.get("items", [])):
        for key in ("title", "organization"):
            if not present(it.get(key, "")):
                flags.append(_flag(f"items.{i}.{key}", "not_in_source", f"{it.get(key)!r} does not appear in the resume text"))
        for j, sk in enumerate(it.get("skills", [])):
            if not present(sk):
                flags.append(_flag(f"items.{i}.skills.{j}", "not_in_source", f"skill {sk!r} does not appear in the resume text"))
    for j, sk in enumerate(data.get("profile", {}).get("skills", [])):
        if not present(sk):
            flags.append(_flag(f"profile.skills.{j}", "not_in_source", f"skill {sk!r} does not appear in the resume text"))
    return flags
