"""LinkedIn / Indeed / Glassdoor through python-jobspy (logged out). One site per Source.

JobSpy runs one site per call here, calls are made one after another with a 2-6 s pause, results are
capped per run, and per-site errors are classified: 429/403-like -> RateLimited (24 h pause);
Glassdoor "location not supported" / no results -> a coverage note, not a failure.

LinkedIn: JobSpy fetches job pages back-to-back with no delay and only *logs* a block there, so it is
called with fetch_description=False (search pages only, which JobSpy paces 3-7 s apart) and each new
job's description is fetched by sources/linkedin_details.py through PoliteClient.

Safety net for every site: JobSpy's warnings (returned ones AND ones it only logs) are read; a throttling
warning, or a batch where most rows came back without a description, is treated as rate-limited.
"""
import logging
import math
import random
import re
import time
from collections.abc import Callable
from datetime import date, datetime

from sources.base import NormalizedJob, tidy_location
from sources.http import RateLimited, SourceError, current_delay, fake_mode
from sources.ingest import SUMMARY_ONLY
from sources.smart_paste import normalize_job_type

JOBSPY_SITES = ("linkedin", "indeed", "glassdoor")
_BLOCKED = re.compile(r"\b(429|403|too many requests|rate.?limit|blocked|forbidden|captcha)\b", re.IGNORECASE)
_COVERAGE = re.compile(r"(location|not (?:supported|available)|no jobs? found|country)", re.IGNORECASE)
_JOB_TYPES = {"fulltime", "parttime", "internship", "contract"}

_THROTTLED = re.compile(r"throttl|blocked|too many requests|\b(429|403|999)\b|authwall|captcha", re.IGNORECASE)
EMPTY_DESCRIPTION_SHARE = 0.6  # a batch where more rows than this lack a description looks throttled
MIN_BATCH_FOR_EMPTY_CHECK = 3

# -> (rows, error message for this site or "", warnings: returned by JobSpy + logged by it)
Scrape = Callable[..., tuple[list[dict], str, list[str]]]


class _Capture(logging.Handler):
    """Collects what JobSpy only logs (e.g. a 429 on a LinkedIn job page)."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def real_scrape(**kw) -> tuple[list[dict], str, list[str]]:
    from jobspy import scrape_jobs  # imported lazily: tests and fake mode never load it

    return run_scrape(scrape_jobs, **kw)


def run_scrape(scrape_jobs: Callable, **kw) -> tuple[list[dict], str, list[str]]:
    """Call JobSpy for one site and collect its error plus every warning (returned or only logged)."""
    logger = logging.getLogger("jobspy")
    capture = _Capture()
    logger.addHandler(capture)
    try:
        df = scrape_jobs(**{**kw, "verbose": 1})  # 1 = warnings are emitted (0 would drop them)
    finally:
        logger.removeHandler(capture)
    site = kw["site_name"][0]
    attrs = df.attrs or {}
    error = str((attrs.get("errors") or {}).get(site, "") or "")
    warnings = [str(w) for w in (attrs.get("warnings") or {}).get(site, []) or []]
    warnings += [m for m in capture.messages if m not in warnings]
    return df.to_dict("records"), error, warnings


def fake_scrape(**kw) -> tuple[list[dict], str, list[str]]:
    from sources.fake import jobspy_rows
    return jobspy_rows(kw["site_name"][0]), "", []


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if type(v).__name__ in ("NaTType",):
        return None
    return v


def _location(v) -> str:
    v = _clean(v)
    if isinstance(v, dict):
        parts = [_clean(v.get("city")), _clean(v.get("state"))]
        parts = [str(p) for p in parts if p]
        if not parts and _clean(v.get("country")):
            parts = [str(v["country"]).title()]
        return tidy_location(", ".join(dict.fromkeys(parts)))
    return tidy_location(str(v or "").strip())


def _date(v) -> date | None:
    v = _clean(v)
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _salary(row: dict) -> tuple[float | None, float | None, str]:
    lo, hi = _clean(row.get("min_amount")), _clean(row.get("max_amount"))
    interval = str(_clean(row.get("interval")) or "").lower()
    if lo is None and hi is None:
        return None, None, ""
    factor = {"monthly": 1, "yearly": 1 / 12}.get(interval)
    if factor is None:  # hourly / daily / weekly: not comparable to a monthly salary, keep it out
        return None, None, ""
    conv = lambda x: round(float(x) * factor) if x is not None else None  # noqa: E731
    return conv(lo), conv(hi), str(_clean(row.get("currency")) or "")


class JobSpySource:
    def __init__(self, site: str, max_results: int = 50, known: set[str] | None = None,
                 scrape: Scrape | None = None, sleep: Callable[[float], None] = time.sleep,
                 delay: tuple[float, float] | None = None, client=None):
        assert site in JOBSPY_SITES
        self.key = site
        self.max_results = max_results
        self.known = known or set()  # site job ids and URLs already stored
        self.scrape = scrape or (fake_scrape if fake_mode() else real_scrape)
        self._sleep, self.delay = sleep, delay if delay is not None else current_delay()
        self.calls = 0
        self.notes: list[str] = []
        self.collected: list[NormalizedJob] = []
        # LinkedIn descriptions are fetched by us, paced and watched (see the module docstring)
        if site == "linkedin" and client is None:
            from sources.http import PoliteClient
            client = PoliteClient(sleep=sleep, wait_first=True)
        self.client = client

    def _call(self, **kw) -> list[dict]:
        if self.calls and self.delay[1] > 0:
            self._sleep(random.uniform(*self.delay))
        self.calls += 1
        try:
            rows, error, warnings = self.scrape(**kw)
        except ValueError as e:  # JobSpy rejects e.g. an unsupported country for this site
            rows, error, warnings = [], str(e), []
        except Exception as e:  # noqa: BLE001 - any library failure is this source's error, not the app's
            raise SourceError(f"{self.key}: {e.__class__.__name__}: {e}") from e
        for w in warnings:
            note = f"JobSpy warning: {w.strip()[:160]}"
            if note not in self.notes:
                self.notes.append(note)
        self._check_throttled(rows, warnings, kw.get("results_wanted") or 0)
        if error:
            if _BLOCKED.search(error):
                code = 403 if re.search(r"403|forbidden", error, re.IGNORECASE) else 429
                raise RateLimited(code, f"https://www.{self.key}.com")
            if self.key == "glassdoor" and _COVERAGE.search(error):
                self.notes.append(f"Glassdoor: {error.strip()[:120]} (little or no Malaysia coverage)")
                return []
            raise SourceError(f"{self.key}: {error.strip()[:200]}")
        return rows

    def _check_throttled(self, rows: list[dict], warnings: list[str], wanted: int) -> None:
        """Safety net: signs of throttling that JobSpy does not report as errors."""
        hits = [w for w in warnings if _THROTTLED.search(w)]
        # "empty page ... (the end of the results, or throttled)" is only suspicious with fewer rows than asked for
        hits = [w for w in hits if not ("end of the results" in w and len(rows) >= wanted)]
        if hits:
            raise RateLimited(429, f"https://www.{self.key}.com")
        if self.key != "linkedin" and len(rows) >= MIN_BATCH_FOR_EMPTY_CHECK:  # LinkedIn rows never carry one now
            empty = sum(1 for r in rows if not str(_clean(r.get("description")) or "").strip())
            if empty / len(rows) > EMPTY_DESCRIPTION_SHARE:
                self.notes.append(f"{empty} of {len(rows)} {self.key} results came back without a description")
                raise RateLimited(429, f"https://www.{self.key}.com")

    def to_normalized(self, row: dict) -> NormalizedJob | None:
        title, url = _clean(row.get("title")), _clean(row.get("job_url"))
        if not title or not url:
            return None
        lo, hi, cur = _salary(row)
        jt = _clean(row.get("job_type"))
        jt = ", ".join(jt) if isinstance(jt, list) else str(jt or "")
        remote = bool(_clean(row.get("is_remote")))
        jid = str(_clean(row.get("id")) or url)
        return NormalizedJob(
            title=str(title).strip(), company=str(_clean(row.get("company")) or "").strip(),
            location=_location(row.get("location")), description=str(_clean(row.get("description")) or "").strip(),
            url=str(url), source=self.key, salary_min=lo, salary_max=hi, salary_currency=cur,
            job_type=normalize_job_type(jt.replace("fulltime", "full time").replace("parttime", "part time")) or jt,
            work_arrangement="Remote" if remote else "", posted_date=_date(row.get("date_posted")),
            extra={"external_ids": {self.key: jid}},
        )

    @staticmethod
    def _summary_only(nj: NormalizedJob) -> NormalizedJob:
        nj.description = f"{nj.title} at {nj.company}\n\n{SUMMARY_ONLY}"
        return nj

    def _add_linkedin_description(self, nj: NormalizedJob) -> None:
        from sources.linkedin_details import fetch_description, job_id_of

        try:
            page = fetch_description(self.client, job_id_of(nj.url, nj.extra["external_ids"][self.key]))
        except RateLimited:
            raise
        except SourceError as e:
            self.notes.append(f"LinkedIn job {nj.url}: {e}; saved without its description")
            self._summary_only(nj)
            return
        nj.description = page["description"]
        if page.get("job_type") and not nj.job_type:
            nj.job_type = normalize_job_type(page["job_type"]) or page["job_type"]

    def fetch(self, search_profile) -> list[NormalizedJob]:
        cap = min(self.max_results, getattr(search_profile, "max_results", 0) or self.max_results)
        job_type = search_profile.job_type if search_profile.job_type in _JOB_TYPES else None
        seen: set[str] = set()
        out = self.collected = []
        for kw in search_profile.keywords:
            for loc in search_profile.locations or ["Malaysia"]:
                if len(out) >= cap:
                    return out
                remote = loc.strip().lower() == "remote"
                where = "Malaysia" if remote else (loc if "malaysia" in loc.lower() else f"{loc}, Malaysia")
                rows = self._call(site_name=[self.key], search_term=kw, location=where, is_remote=remote or None,
                                  results_wanted=cap - len(out), country_indeed="malaysia",
                                  hours_old=(search_profile.days or 0) * 24 or None, job_type=job_type,
                                  description_format="markdown", fetch_description=False, verbose=0)
                blocked: RateLimited | None = None
                for row in rows:
                    nj = self.to_normalized(row)
                    if nj is None:
                        continue
                    jid = nj.extra["external_ids"][self.key]
                    if jid in seen or jid in self.known or nj.url in self.known:
                        continue
                    seen.add(jid)
                    self.known.add(jid)  # a later search profile in the same run skips it
                    if self.key == "linkedin" and not nj.description:
                        if blocked is None:
                            try:
                                self._add_linkedin_description(nj)
                            except RateLimited as e:
                                blocked = e  # stop asking; this and the remaining rows are kept as summaries
                        if blocked is not None:
                            self._summary_only(nj)
                    out.append(nj)
                    if len(out) >= cap:
                        break
                if blocked is not None:
                    kept = sum(1 for j in out if j.description.endswith(SUMMARY_ONLY))
                    self.notes.append(f"job pages blocked: saved {kept} job(s) from the search results only")
                    raise blocked
                if len(out) >= cap:
                    return out
        if self.key == "glassdoor" and not out and not self.notes:
            self.notes.append("Glassdoor returned no jobs for these searches (little or no Malaysia coverage)")
        return out
