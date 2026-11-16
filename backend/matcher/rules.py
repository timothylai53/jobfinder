"""Regex/heuristic extraction of years, education, languages from JD clauses, plus location checks."""
import re
from dataclasses import dataclass, field

from matcher.jd_sections import Clause

# ---------- years of experience ----------

_WORD_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_NUM = r"(\d+(?:\.\d+)?|" + "|".join(_WORD_NUM) + r")"
_YEARS = re.compile(
    _NUM + r"\s*(?:\(\s*\d+\s*\)\s*)?\+?\s*(?:(?:-|–|to)\s*" + _NUM + r"\s*\+?\s*)?"
    r"(?:years?|yrs?)(?:'s?)?\b",
    re.IGNORECASE,
)
_EXPERIENCE_CONTEXT = re.compile(r"\b(experience|exp\b|experienced|working|work|industry|hands-on|track record)", re.IGNORECASE)
_FRESH_GRAD = re.compile(
    r"\bfresh\s+grad(uate)?s?\b[^.;]*\b(welcome|encouraged|may apply|can apply|are invited|considered)|"
    r"\b(fresh\s+grad(uate)?s?|entry[\s-]level|no (prior )?experience)\s+(is\s+|are\s+)?(welcome|required|needed|accepted)|"
    r"\bno experience required\b|\bfresh graduates? (are )?welcome\b",
    re.IGNORECASE,
)


def _to_num(tok: str) -> float:
    tok = tok.lower()
    return float(_WORD_NUM[tok]) if tok in _WORD_NUM else float(tok)


@dataclass
class YearsRequirement:
    years: float | None  # None = not specified
    evidence: str = ""
    fresh_grad_ok: bool = False


def extract_years(clauses: list[Clause]) -> YearsRequirement:
    """Largest lower bound among required clauses that talk about experience.

    A JD that explicitly welcomes fresh graduates is treated as requiring 0 years.
    """
    best: YearsRequirement = YearsRequirement(None)
    fresh = next((c.text for c in clauses if c.kind != "ignored" and _FRESH_GRAD.search(c.text)), None)
    for c in clauses:
        if c.kind != "required" or not _EXPERIENCE_CONTEXT.search(c.text):
            continue
        for m in _YEARS.finditer(c.text):
            low = _to_num(m.group(1))
            if low > 30:
                continue
            if best.years is None or low > best.years:
                best = YearsRequirement(low, c.text)
    if fresh is not None:
        return YearsRequirement(0, fresh, fresh_grad_ok=True)
    return best


# ---------- education ----------

EDU_LEVELS = {"SPM": 1, "STPM": 2, "Diploma": 3, "Degree": 4, "Master": 5, "PhD": 6}
_EDU_PATTERNS = [
    ("PhD", re.compile(r"\b(ph\.?\s?d|doctorate|doctoral)\b", re.IGNORECASE)),
    ("Master", re.compile(r"\b(master'?s?|msc|m\.sc|mba|postgraduate)\b", re.IGNORECASE)),
    ("Degree", re.compile(r"\b(bachelor'?s?|degree|bsc|b\.sc|beng|b\.eng|bcs|undergraduate|graduate in)\b", re.IGNORECASE)),
    # DVM / DKM / DLKM: Malaysian vocational and skills diplomas
    ("Diploma", re.compile(r"\b(diploma|advanced diploma|dvm|dkm|dlkm)\b", re.IGNORECASE)),
    ("STPM", re.compile(r"\b(stpm|a-?levels?|foundation|matriculation|uec)\b", re.IGNORECASE)),
    # SVM / SKM: vocational and skills certificates, counted at SPM level
    ("SPM", re.compile(r"\b(spm|o-?levels?|svm|skm|sijil vokasional|sijil kemahiran)\b", re.IGNORECASE)),
]
_COMPUTING_FIELDS = (
    "computer science", "software engineering", "information technology", "computing",
    "computer engineering", "information systems", "data science", "it", "ict", "cybersecurity",
    "artificial intelligence", "multimedia", "computer", "software",
)
_FIELD_PATTERN = re.compile(
    r"\b(computer science|software engineering|information technology|computing|computer engineering|"
    r"information systems?|data science|cyber\s?security|artificial intelligence|multimedia|"
    r"electrical(?: and electronics?)? engineering|electronics? engineering|mechanical engineering|"
    r"mathematics|statistics|physics|engineering|business|accounting|finance|marketing|(?-i:IT|ICT))\b",
    re.IGNORECASE,
)
_RELATED = re.compile(r"\b(related|relevant|equivalent|similar|any)\s+(field|discipline|area|major|qualification)", re.IGNORECASE)
_ANY_FIELD = re.compile(r"\bany\s+(field|discipline)\b", re.IGNORECASE)


@dataclass
class EducationRequirement:
    level: str | None = None
    fields: list[str] = field(default_factory=list)
    related_ok: bool = False
    any_field: bool = False
    mandatory: bool = False
    evidence: str = ""


def extract_education(clauses: list[Clause]) -> EducationRequirement:
    """Lowest education level mentioned (e.g. "Diploma or Degree" -> Diploma)."""
    found: EducationRequirement | None = None
    for c in clauses:
        if c.kind == "ignored":
            continue
        # "Master's degree" / "Doctoral degree" name one level, not Degree as well.
        text = re.sub(r"\b(master'?s?|doctoral|doctorate)\s+degree", r"\1", c.text, flags=re.IGNORECASE)
        levels = [lvl for lvl, pat in _EDU_PATTERNS if pat.search(text)]
        if not levels:
            continue
        # "graduate in" / "degree" in a sentence about fresh graduates is not a requirement.
        if re.search(r"\bfresh\s+grad", c.text, re.IGNORECASE) and not re.search(r"\b(bachelor|diploma|degree in)", c.text, re.IGNORECASE):
            continue
        low = min(levels, key=lambda lvl: EDU_LEVELS[lvl])
        fields = sorted({f.lower() for f in _FIELD_PATTERN.findall(c.text)})
        if "information technology" in fields:  # "Information Technology (IT)" names one field, not two
            fields = [f for f in fields if f not in ("it", "ict")]
        req = EducationRequirement(
            level=low,
            fields=fields,
            related_ok=bool(_RELATED.search(c.text)),
            any_field=bool(_ANY_FIELD.search(c.text)),
            mandatory=c.kind == "required",
            evidence=c.text,
        )
        # Prefer the mandatory requirement; among equals keep the first one.
        if found is None or (req.mandatory and not found.mandatory):
            found = req
    return found or EducationRequirement()


def is_computing_field(f: str) -> bool:
    f = f.lower()
    return any(re.search(r"\b" + re.escape(k) + r"\b", f) for k in _COMPUTING_FIELDS)


def field_matches(my_field: str, req: EducationRequirement) -> bool | None:
    """True/False, or None when the JD names no field."""
    if not req.fields or req.any_field:
        return None
    mine = my_field.lower().strip()
    if not mine:
        return False
    if any(f in mine or mine in f for f in req.fields):
        return True
    computing_req = any(is_computing_field(f) for f in req.fields)
    if computing_req and is_computing_field(mine):
        # Computing fields are treated as one family (CS ~ SE ~ IT).
        return True
    return False


# ---------- languages ----------

LANGUAGES = {
    "English": r"english",
    "Bahasa Malaysia": r"bahasa(?:\s+(?:malaysia|melayu))?|\bBM\b|malay",
    "Mandarin": r"mandarin|chinese(?!\s+new\s+year)",
    "Cantonese": r"cantonese",
    "Tamil": r"tamil",
    "Japanese": r"japanese",
    "Korean": r"korean",
    "Thai": r"\bthai\b",
    "Vietnamese": r"vietnamese",
    "Indonesian": r"indonesian|bahasa indonesia",
}
_LANG_PATTERNS = {k: re.compile(r"(?<![A-Za-z])(?:" + v + r")(?![A-Za-z])", re.IGNORECASE) for k, v in LANGUAGES.items()}
_LANG_PATTERNS["Bahasa Malaysia"] = re.compile(r"\bbahasa(?:\s+(?:malaysia|melayu))?\b|\bBM\b|\bmalay\b(?!sia)", re.IGNORECASE)
_LANG_CONTEXT = re.compile(
    r"\b(language|languages|speak|speaking|spoken|written|write|communicat\w*|proficien\w*|fluen\w*|"
    r"command of|bilingual|multilingual|verbal|conversant|literate)\b",
    re.IGNORECASE,
)


@dataclass
class LanguageRequirement:
    language: str
    mandatory: bool
    evidence: str


def extract_languages(clauses: list[Clause]) -> list[LanguageRequirement]:
    out: dict[str, LanguageRequirement] = {}
    for c in clauses:
        if c.kind == "ignored" or not _LANG_CONTEXT.search(c.text):
            continue
        for lang, pat in _LANG_PATTERNS.items():
            if lang == "Bahasa Malaysia" and re.search(r"bahasa indonesia", c.text, re.IGNORECASE):
                continue
            if pat.search(c.text):
                mandatory = c.kind == "required"
                prev = out.get(lang)
                if prev is None or (mandatory and not prev.mandatory):
                    out[lang] = LanguageRequirement(lang, mandatory, c.text)
    return list(out.values())


def normalize_language(name: str) -> str | None:
    for lang, pat in _LANG_PATTERNS.items():
        if pat.fullmatch(name.strip()) or pat.search(name.strip()):
            return lang
    return None


# ---------- location ----------

# Shorthand / alternate spellings for what I type as a preferred location.
LOCATION_ALIASES = {
    "kl": "kuala lumpur", "pj": "petaling jaya", "jb": "johor bahru", "kk": "kota kinabalu",
    "penang": "pulau pinang", "pulau pinang": "penang", "malacca": "melaka", "melaka": "malacca",
    "wp kuala lumpur": "kuala lumpur", "wilayah persekutuan kuala lumpur": "kuala lumpur",
}
_REMOTE = re.compile(r"\b(remote|work from home|wfh|anywhere)\b", re.IGNORECASE)


def _loc_variants(pref: str, location_map: dict[str, list[str]]) -> list[str]:
    """Names that count as a match for one preferred location (original spelling kept).

    A preferred state (e.g. Selangor) also matches every town/area listed under it in the map.
    """
    base = pref.strip()
    names = [base]
    if base.lower() in LOCATION_ALIASES:
        names.append(LOCATION_ALIASES[base.lower()])
    states = {k.lower(): v for k, v in location_map.items()}
    out: dict[str, str] = {}
    for n in names:
        for v in [n, *states.get(n.lower(), [])]:
            if v.strip():
                out.setdefault(v.strip().lower(), v.strip())
    return sorted(out.values(), key=len, reverse=True)


def is_remote(job_location: str, jd: str) -> bool:
    if _REMOTE.search(job_location or ""):
        return True
    return bool(re.search(r"\b(fully remote|100% remote|remote[- ]first|work from home|remote work(ing)? (is )?(available|allowed|option))\b", jd or "", re.IGNORECASE))


def location_matches(job_location: str, preferred: list[str],
                     location_map: dict[str, list[str]] | None = None) -> tuple[str, str] | None:
    """Return (preferred location, name found in the job location), or None.

    Whole-word match, so "KL" does not match "Klang".
    """
    from sources.base import tidy_location
    jl = tidy_location(job_location or "")
    for p in preferred:
        if p.strip().lower() in ("", "remote"):
            continue
        for v in _loc_variants(p, location_map or {}):
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(v) + r"(?![A-Za-z0-9])", jl, re.IGNORECASE):
                return p, v
    return None
