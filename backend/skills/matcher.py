"""Find dictionary skills in free text (case-insensitive, word-boundary aware, alias-aware)."""
import re
from dataclasses import dataclass, field

# Terms that are also common English words (or too short to be safe) only match
# when written with the same capitalization as in the dictionary.
CASE_SENSITIVE_TERMS = {
    "REST", "Spring", "Express", "Swift", "Rust", "Node", "Rails", "Spark",
    "Excel", "Agile", "Kanban", "Go", "Dart", "Ruby", "Mongo", "Leadership",
}

# A term may not be glued to letters/digits or to symbols that are part of other
# skill names (C vs C++ / C#, Java vs JavaScript, .NET vs ASP.NET, R vs R&D).
_BEFORE = r"(?<![A-Za-z0-9+#&.\-])"
_AFTER = r"(?![A-Za-z0-9+#&]|\.[A-Za-z0-9]|-[A-Za-z])"


@dataclass
class SkillDef:
    name: str
    aliases: list[str] = field(default_factory=list)
    category: str = "other"


def _term_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.strip()).replace(r"\ ", r"[\s\-]+")
    flags = 0 if (len(term) <= 2 or term in CASE_SENSITIVE_TERMS) else re.IGNORECASE
    return re.compile(_BEFORE + escaped + _AFTER, flags)


class SkillMatcher:
    def __init__(self, skills: list[SkillDef]):
        self.skills = skills
        self._patterns: list[tuple[str, list[re.Pattern]]] = []
        for s in skills:
            terms = sorted({t for t in [s.name, *s.aliases] if t.strip()}, key=len, reverse=True)
            self._patterns.append((s.name, [_term_pattern(t) for t in terms]))
        self._category = {s.name: s.category for s in skills}
        self._by_lower = {s.name.lower(): s.name for s in skills}
        for s in skills:
            for a in s.aliases:
                self._by_lower.setdefault(a.lower(), s.name)

    def find(self, text: str) -> list[str]:
        """Canonical names of skills mentioned in text, in dictionary order."""
        if not text:
            return []
        return [name for name, pats in self._patterns if any(p.search(text) for p in pats)]

    def find_spans(self, text: str) -> list[tuple[int, int, str]]:
        """(start, end, canonical name) for each mention, left to right; overlaps keep the longer match."""
        if not text:
            return []
        hits = [(m.start(), m.end(), name) for name, pats in self._patterns for p in pats for m in p.finditer(text)]
        hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        out: list[tuple[int, int, str]] = []
        for h in hits:
            if out and h[0] < out[-1][1]:
                continue  # inside a longer match already taken (e.g. "Java" inside "Java EE")
            out.append(h)
        return out

    def category(self, name: str) -> str:
        return self._category.get(name, "other")

    def canonical(self, term: str) -> str | None:
        """Map a free-typed skill (name or alias) to its canonical name."""
        return self._by_lower.get(term.strip().lower())

    def normalize_list(self, terms: list[str]) -> list[str]:
        """Canonicalize a list of skill names; unknown ones are kept as typed."""
        out: list[str] = []
        for t in terms:
            if not t.strip():
                continue
            c = self.canonical(t) or t.strip()
            if c not in out:
                out.append(c)
        return out
