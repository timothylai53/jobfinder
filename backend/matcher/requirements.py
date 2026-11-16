"""Turn the skills mentioned in one JD clause into requirements.

A requirement is either one skill, or a group of alternatives that is met by any one of them:
"C#/ Java/ Javascript or equivalent", "Java, Python or Go", "at least one of AWS, Azure, GCP".
Plain lists without an alternative signal ("JavaScript, HTML and CSS") stay separate requirements.
"""
import re
from dataclasses import dataclass, field

from skills.matcher import SkillMatcher

# Text allowed between two skills of the same run.
_SEP = re.compile(r"\s*(?:/|\||,|;|\bor\b|\band/or\b|,\s*or\b)\s*", re.IGNORECASE)
_ALT_SEP = re.compile(r"/|\||\bor\b", re.IGNORECASE)
_ALT_SIGNAL = re.compile(
    # "at least one (1) year" is about experience, not a list of alternatives
    r"\b(at least one(?!\s*(?:\(\d+\)\s*)?(?:years?|yrs?)\b)|one of|any of|any one of|either|one or more of|"
    r"or equivalent|or similar|or other)\b",
    re.IGNORECASE,
)
_EQUIVALENT_AFTER = re.compile(r"^\W{0,3}\s*(?:or|and/or)\s+(?:an?\s+)?(?:equivalent|similar|other|related)\b", re.IGNORECASE)
# "Or equivalent" can stand in for any skill of the same kind; these kinds are too vague for that.
NO_EQUIVALENT_CATEGORIES = {"soft", "other", "concept", "process"}
# Finer families inside a category, where "same category" would be too loose
# (Firebase is a database, but not an equivalent of MySQL).
EQUIVALENCE_FAMILIES = [
    {"SQL", "MySQL", "PostgreSQL", "Microsoft SQL Server", "Oracle Database", "SQLite"},
    {"MongoDB", "Redis", "Firebase", "DynamoDB", "Elasticsearch"},
]


@dataclass
class Requirement:
    skills: list[str]
    equivalent_ok: bool = False  # "... or equivalent": a same-kind skill also counts
    clause: str = ""

    @property
    def is_group(self) -> bool:
        return len(self.skills) > 1

    @property
    def key(self) -> tuple:
        return tuple(sorted(self.skills))


@dataclass
class ClauseRequirements:
    hard: list[Requirement] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)


def from_clause(text: str, matcher: SkillMatcher, score_soft: bool = False) -> ClauseRequirements:
    spans = matcher.find_spans(text)
    out = ClauseRequirements()
    if not spans:
        return out

    # 1. Runs of skills separated only by "/", ",", "or", ...
    runs: list[list[tuple[int, int, str]]] = [[spans[0]]]
    seps: list[list[str]] = [[]]
    for prev, cur in zip(spans, spans[1:]):
        between = text[prev[1]:cur[0]]
        if _SEP.fullmatch(between):
            runs[-1].append(cur)
            seps[-1].append(between)
        else:
            runs.append([cur])
            seps.append([])

    prev_end = 0
    for run, sp in zip(runs, seps):
        # "at least one of ..." only applies to the list right after it; "... or equivalent" to the one before.
        equivalent = bool(_EQUIVALENT_AFTER.search(text[run[-1][1]:]))
        signal = bool(_ALT_SIGNAL.search(text[prev_end:run[0][0]])) or equivalent
        prev_end = run[-1][1]
        names = list(dict.fromkeys(n for _, _, n in run))
        if not score_soft:
            soft = [n for n in names if matcher.category(n) == "soft"]
            out.soft += [n for n in soft if n not in out.soft]
            names = [n for n in names if n not in soft]
        if not names:
            continue
        alternatives = len(names) > 1 and (any(_ALT_SEP.search(s) for s in sp) or signal)
        if alternatives:
            out.hard.append(Requirement(names, equivalent, text))
        else:
            out.hard += [Requirement([n], equivalent and len(names) == 1, text) for n in names]
    return out


def evidence_for(req: Requirement, have: dict[str, list[str]], matcher: SkillMatcher) -> tuple[list[str], list[str]]:
    """Return (skills I have from the group, same-kind skills that count via 'or equivalent')."""
    direct = [s for s in req.skills if have.get(s)]
    if direct or not req.equivalent_ok:
        return direct, []
    family = next((f for f in EQUIVALENCE_FAMILIES if set(req.skills) <= f), None)
    if family is not None:
        return [], [s for s in have if have[s] and s in family]
    cats = {matcher.category(s) for s in req.skills} - NO_EQUIVALENT_CATEGORIES
    return [], [s for s in have if have[s] and matcher.category(s) in cats]
