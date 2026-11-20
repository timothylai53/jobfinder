"""Turn a whole copied job page (Ctrl+A, Ctrl+C) into a job draft.

Works offline on text only: no fetching, no browser automation. A site-specific recognizer
(JobStreet) runs first; anything else goes through a cautious generic fallback whose header
fields are always marked "please check".
"""
import re
from dataclasses import dataclass, field

SITE_NAMES = {"jobstreet", "jobstreet by seek", "seek", "linkedin", "indeed", "glassdoor", "hiredly", "maukerja"}

# Whole lines that are page chrome (compared lower-case, trailing punctuation stripped).
# They are never used as title / company / location.
NAV_LINES = {
    "skip to content", "skip to main content", "main content", "menu", "home", "job search", "jobs", "people",
    "people search", "companies", "learning", "games", "profile", "career advice", "company reviews",
    "explore companies", "explore careers", "explore salaries", "community", "sign in", "sign up", "join now",
    "join", "log in", "login", "register", "register for free", "employer site", "for employers", "employers",
    "post a job", "post a job ad", "my network", "messaging", "notifications", "me", "for business",
    "try premium", "saved searches", "saved jobs", "job applications", "download apps", "job seekers",
}
NOISE_LINES = NAV_LINES | {
    "apply", "apply now", "quick apply", "easy apply", "apply on company website", "save", "saved", "share",
    "show more", "show less", "see more", "see less", "view all jobs", "view more jobs", "follow", "following",
    "back", "back to search results", "next", "previous", "close", "dismiss", "report", "report this job",
    "more", "more options", "copy link", "send in a private message", "share via", "recruiter", "promoted",
    "actively recruiting", "be an early applicant", "how you match", "show match details", "beta",
    "is this information helpful", "yes", "no", "retry premium for free", "job alert", "create job alert",
    "set alert", "get notified about new jobs", "listed", "view job", "new", "high application volume",
}
NOISE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"^posted (on )?\d+[a-z]* ago$", r"^posted \d+\s*(minute|hour|day|week|month)s? ago$", r"^\d+\s*[dhwm] ago$",
        r"^(reposted )?\d+\s*(minute|hour|day|week|month)s? ago$", r"^\d+ applicants?$", r"^over \d+ applicants?$",
        r"^\d+ (people )?clicked apply$", r"^\d+ notifications?$", r"^\d+[,\d]* (followers|employees)",
        r"^page \d+ of \d+$", r"^\d+(\.\d)?$", r"^·$", r"^.$", r" logo$",
    )
]
# Once the description has started, these lines mark where the page tail begins.
TAIL_MARKERS = re.compile(
    r"^(similar jobs|people also viewed|more jobs|recommended jobs|jobs you might like|jobs you may be interested in|"
    r"more jobs from|explore collaborative articles|report this job( advert)?|be careful|employer questions|"
    r"your application will include|set alert for similar jobs|looking for talent\??|job seekers|"
    r"©|copyright|seniority level|similar searches|referrals increase your chances|"
    r"meet the hiring team|show more jobs like this|career advice|related searches|"
    r"what can i earn as|are these jobs right for you|discover more|company profile)\b",
    re.IGNORECASE,
)
DESC_START = re.compile(r"^(about the job|job description|about the role|job summary|description)$", re.IGNORECASE)

SALARY = re.compile(
    r"(?:RM|MYR)\s?(\d[\d,.]*)\s*(k)?\s*(?:-|–|—|to)\s*(?:RM|MYR)?\s?(\d[\d,.]*)\s*(k)?"
    r"|(?:RM|MYR)\s?(\d[\d,.]*)\s*(k)?",
    re.IGNORECASE,
)
JOB_TYPE = re.compile(r"\b(full[\s-]?time|part[\s-]?time|contract(?:/temp)?|temporary|internship|casual/vacation|freelance)\b",
                      re.IGNORECASE)
ARRANGEMENT = re.compile(r"^(hybrid|remote|on-?site|work from home)$", re.IGNORECASE)
ARRANGEMENT_SUFFIX = re.compile(r"\s*\((hybrid|remote|on-?site|work from home)\)\s*$", re.IGNORECASE)
LOCATION_HINT = re.compile(r"\b(malaysia|remote|hybrid|on-site|federal territory|wilayah persekutuan)\b", re.IGNORECASE)
COMPANY_HINT = re.compile(r"\b(sdn\.?\s*bhd\.?|bhd\.?|berhad|plc|pte\.?\s*ltd\.?|ltd\.?|inc\.?|llc|group|technologies|"
                          r"solutions|labs|systems|consulting|bank)\b", re.IGNORECASE)

_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\((?:https?://[^)\s]*)\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]*)\)")
_URL = re.compile(r"https?://[^\s)\]>\"']+")
# Words some pages glue onto the previous text when copied ("Posted 4d agoHigh application volume").
_GLUED = re.compile(r"(?<=\S)(?=(View all jobs|High application volume|Be an early applicant|Don[’']t provide|"
                    r"Learn how to protect yourself)\b)")


@dataclass
class PasteDraft:
    title: str = ""
    company: str = ""
    location: str = ""
    work_arrangement: str = ""  # Hybrid / Remote / On-site
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    job_type: str = ""
    salary_undisclosed: bool = False  # the ad says so explicitly ("Salary undisclosed")
    url: str = ""
    description: str = ""
    detected: list[str] = field(default_factory=list)   # fields filled in
    uncertain: list[str] = field(default_factory=list)  # filled, but a guess: show "please check"
    source: str = "generic"  # which recognizer produced this
    removed_lines: int = 0


def norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("⁠", "").replace("​", "")).strip()


def key(line: str) -> str:
    return norm(line).lower().rstrip(".:!·").strip()


def is_noise(line: str) -> bool:
    k = key(line)
    if not k or k in NOISE_LINES or k in SITE_NAMES:
        return True
    return any(p.search(k) for p in NOISE_PATTERNS)


def is_nav(line: str) -> bool:
    """Navigation words and logo alt texts: never a title, company or location."""
    k = key(line)
    return k in NAV_LINES or k in SITE_NAMES or k.endswith(" logo") or len(k) <= 1


def preprocess(text: str) -> tuple[str, list[str]]:
    """Undo copy artefacts: Markdown links -> their text, glued words split onto their own line.
    Returns the cleaned text and every URL that was in the paste."""
    text = text.replace("\r", "").replace("⁠", "").replace("​", "")
    urls = _URL.findall(text)
    text = _MD_IMAGE.sub(lambda m: f"\n{m.group(1)}\n" if m.group(1) else "", text)
    text = _MD_LINK.sub(r"\1", text)
    text = re.sub(r"\bago(?=[A-Z])", "ago\n", text)
    text = _GLUED.sub("\n", text)
    text = re.sub(r"^(\s*)[*•]\s+", r"\1- ", text, flags=re.MULTILINE)
    return text, urls


def job_url(urls: list[str], raw: str) -> str:
    """A link to this job, only when the paste really contains one. Never pasted text."""
    for u in urls:
        m = re.search(r"https?://([a-z]{2,3}\.jobstreet\.com)/(?:[^\s?#]*/)?job/(\d+)", u) \
            or re.search(r"https?://([a-z]{2,3}\.jobstreet\.com)/[^\s]*[?&]jobId=(\d+)", u)
        if m:
            return f"https://{m.group(1)}/job/{m.group(2)}"
        m = re.search(r"linkedin\.com/jobs/view/(?:[^/\s?]*-)?(\d+)", u)
        if m:
            return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
    s = raw.strip()
    if re.fullmatch(r"https?://\S+", s):  # the paste is just a URL
        return s
    return ""


def normalize_job_type(s: str) -> str:
    m = JOB_TYPE.search(s)
    if not m:
        return ""
    t = m.group(1).lower().replace("-", " ")
    t = re.sub(r"\s+", " ", t)
    t = {"fulltime": "full time", "parttime": "part time"}.get(t, t)
    return t[:1].upper() + t[1:]


def split_arrangement(location: str) -> tuple[str, str]:
    m = ARRANGEMENT_SUFFIX.search(location)
    if not m:
        return location.strip(), ""
    return location[: m.start()].strip(), arrangement_label(m.group(1))


def arrangement_label(s: str) -> str:
    s = s.lower()
    return "On-site" if s.replace("-", "") == "onsite" else ("Remote" if s in ("remote", "work from home") else "Hybrid")


def _money(num: str, k: str | None) -> float | None:
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    return v * 1000 if k else v


def find_salary(text: str) -> tuple[float | None, float | None, str]:
    for m in SALARY.finditer(text):
        if m.group(1):
            lo, hi = _money(m.group(1), m.group(2)), _money(m.group(3), m.group(4) or m.group(2))
        else:
            lo = hi = _money(m.group(5), m.group(6))
        if lo is None or lo < 100:  # "RM 5" is not a salary
            continue
        return lo, (hi if hi != lo else None), "MYR"
    return None, None, ""


def location_names(location_map: dict[str, list[str]]) -> list[str]:
    names = set(location_map)
    for towns in location_map.values():
        names.update(t for t in towns if len(t) > 2)
    return sorted(names, key=len, reverse=True)


def looks_like_location(line: str, names: list[str]) -> bool:
    if len(line) > 90 or SALARY.search(line) or is_nav(line):
        return False
    if LOCATION_HINT.search(line):
        return True
    return any(re.search(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])", line, re.IGNORECASE) for n in names)


def looks_like_title(line: str) -> bool:
    words = line.split()
    return 1 <= len(words) <= 12 and len(line) <= 100 and not line.endswith(".") and not SALARY.search(line) \
        and not re.search(r"https?://|@", line) and not is_nav(line)


def tidy_description(lines: list[str]) -> str:
    """Join JD lines, keeping single blank lines between paragraphs and dropping noise lines."""
    out: list[str] = []
    for ln in lines:
        s = norm(ln)
        if not s:
            if out and out[-1]:
                out.append("")
            continue
        if is_noise(s):
            continue
        out.append(s)
    return "\n".join(out).strip()


def _finish(d: PasteDraft, urls: list[str], raw: str) -> PasteDraft:
    d.url = job_url(urls, raw)
    d.detected = [f for f, v in (("title", d.title), ("company", d.company), ("location", d.location),
                                 ("work_arrangement", d.work_arrangement), ("salary", d.salary_min),
                                 ("job_type", d.job_type), ("url", d.url)) if v]
    d.uncertain = [f for f in d.uncertain if f in d.detected]
    return d


def extract(text: str, location_map: dict[str, list[str]] | None = None) -> PasteDraft:
    from sources.paste_jobstreet import recognize as jobstreet

    clean, urls = preprocess(text)
    raw_lines = [norm(row) for row in clean.split("\n")]
    names = location_names(location_map or {})
    d = jobstreet(raw_lines, names) or generic(raw_lines, names)
    return _finish(d, urls, text)


def generic(raw_lines: list[str], names: list[str]) -> PasteDraft:
    """Fallback for any site: header fields are guesses, so they are all marked uncertain."""
    lines = [row for row in raw_lines if row]
    d = PasteDraft(source="generic")

    start = next((i for i, row in enumerate(lines) if DESC_START.match(key(row))), None)
    header_end = start
    if start is None:
        top = lines[:40]
        marks = [i for i, row in enumerate(top) if re.search(r"^posted\b|\bago$|^(quick |easy )?apply( now)?$|^save$", key(row))]
        header_end = marks[-1] + 1 if marks else 0
        desc_lines = lines[header_end:]
    else:
        # LinkedIn's "About the job" is page chrome; real JD headings ("About the role") stay in the text.
        desc_lines = lines[start + 1:] if key(lines[start]) in ("about the job", "description") else lines[start:]
    header = [row for row in lines[:header_end] if not is_noise(row)] if header_end else []

    cut = len(desc_lines)
    for i, row in enumerate(desc_lines):
        if TAIL_MARKERS.match(key(row)) and i >= 1:
            cut = i
            break
    tail = desc_lines[cut:]
    body = [row for row in desc_lines[:cut] if not is_noise(row)]
    d.removed_lines = len(lines) - len(body) - len(header)

    # LinkedIn joins "Company · Location · 2 days ago · 87 applicants" on one line.
    expanded: list[str] = []
    for row in header:
        expanded.extend(p.strip() for p in re.split(r"\s+·\s+", row) if p.strip() and not is_noise(p))
    for row in expanded:
        if is_nav(row):
            continue
        if ARRANGEMENT.match(row):
            d.work_arrangement = d.work_arrangement or arrangement_label(row)
            continue
        if not d.title and looks_like_title(row) and not looks_like_location(row, names) and not JOB_TYPE.fullmatch(row):
            d.title = row
            continue
        if d.title and not d.company and looks_like_title(row) and not looks_like_location(row, names) \
                and not JOB_TYPE.search(row) and not re.search(r"\(.*\)$", row):
            d.company = row
            continue
        if not d.location and looks_like_location(row, names) and not JOB_TYPE.fullmatch(row):
            d.location, arr = split_arrangement(row)
            d.work_arrangement = d.work_arrangement or arr
            continue
        if not d.job_type and JOB_TYPE.search(row) and len(row) < 40:
            d.job_type = normalize_job_type(row)
    if not d.title and body and looks_like_title(body[0]) and not header:
        d.title = body[0]  # plain JD paste whose first line is the title
        body = body[1:]
        if body and not d.company and COMPANY_HINT.search(body[0]) and looks_like_title(body[0]):
            d.company = body.pop(0)
        if body and not d.location and looks_like_location(body[0], names) and len(body[0]) < 60:
            d.location = body.pop(0)

    if not d.job_type:  # LinkedIn criteria block: "Employment type" / "Full-time"
        for i, row in enumerate(tail):
            if key(row) == "employment type" and i + 1 < len(tail):
                d.job_type = normalize_job_type(tail[i + 1])
                break

    lo, hi, cur = find_salary("\n".join(header) or "\n".join(body[:15]))
    if lo is None:
        lo, hi, cur = find_salary("\n".join(body))
    d.salary_min, d.salary_max, d.salary_currency = lo, hi, cur
    d.description = "\n".join(body).strip()
    d.uncertain = ["title", "company", "location", "work_arrangement", "salary", "job_type"]
    return d
