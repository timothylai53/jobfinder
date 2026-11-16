"""The one HTTP client every source module uses: polite by construction.

- one request at a time (each source owns its client), random 2-6 s pause between requests;
- a realistic but honest user agent (a browser-style prefix plus who we really are);
- logged-out only: no cookies are stored, no credentials exist anywhere;
- HTTP 429 / 403 (and LinkedIn's 999 "request denied") raise RateLimited immediately (the caller pauses
  the source for 24 h);
- every request is logged (method, URL, status) to data/logs/requests.log, and every block or error
  response is saved to data/debug/ (status, headers, first 2 KB of the body), so a failure can be
  diagnosed offline without asking the site again.

Tests and the fake-replay mode swap the transport (httpx.MockTransport); nothing else changes.
"""
import json
import os
import random
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) JobFinder/0.2 "
              "(personal job search tool; single user; low request rate)")


class SourceError(Exception):
    """A source could not be read (network error, unexpected status)."""


class SchemaChanged(SourceError):
    """The site answered, but not in the shape we expect (the site changed its API)."""


BLOCK_STATUSES = (403, 429, 999)


class RateLimited(SourceError):
    """HTTP 429 / 403 / 999: the site wants us to stop. Never retried."""

    def __init__(self, status: int, url: str, saved: str = ""):
        super().__init__(f"HTTP {status} from {httpx.URL(url).host}" + (f" (response saved to {saved})" if saved else ""))
        self.status = status
        self.saved = saved


# ---------- local diagnostics (never leave the laptop) ----------

BODY_PREVIEW = 2048
_REDACTED_HEADERS = {"set-cookie", "cookie", "authorization"}  # site session cookies are not worth keeping


def _data_dir() -> Path:
    from app.config import DATA_DIR
    return DATA_DIR


def save_debug(name: str, data) -> str:
    """Write a JSON file to data/debug/ and return its path."""
    d = _data_dir() / "debug"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}-{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str)[:200_000], encoding="utf-8")
    return str(path)


def _headers(h: httpx.Headers) -> dict[str, str]:
    return {k: ("<redacted>" if k.lower() in _REDACTED_HEADERS else v) for k, v in h.multi_items()}


def save_response(r: httpx.Response, why: str) -> str:
    """Save a blocked / failed / unexpected response: enough to tell a bot-protection page from an API refusal."""
    body = r.content[:BODY_PREVIEW].decode(r.encoding or "utf-8", errors="replace")
    host = r.request.url.host if r.request else "unknown"
    return save_debug(f"response-{host}-{r.status_code}", {
        "why": why,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "method": r.request.method if r.request else "",
        "url": str(r.request.url) if r.request else "",
        "final_url": str(r.url),
        "redirects": [{"status": h.status_code, "url": str(h.url), "location": h.headers.get("location", "")}
                      for h in r.history],
        "status": r.status_code,
        "request_headers": _headers(r.request.headers) if r.request else {},
        "response_headers": _headers(r.headers),
        "body_bytes": len(r.content),
        f"body_first_{BODY_PREVIEW}_bytes": body,
    })


def log_request(method: str, url: str, outcome: str) -> None:
    """One line per request to data/logs/requests.log (local only)."""
    try:
        d = _data_dir() / "logs"
        d.mkdir(parents=True, exist_ok=True)
        with (d / "requests.log").open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {method} {url} -> {outcome}\n")
    except OSError:
        pass  # diagnostics must never break a fetch


# Pause between requests (seconds). Real runs: 2-6 s. Tests set (0, 0); fake replay mode uses a short one.
DEFAULT_DELAY: tuple[float, float] = (2.0, 6.0)
FAKE_MODE_DELAY: tuple[float, float] = (0.2, 0.6)


def current_delay() -> tuple[float, float]:
    return FAKE_MODE_DELAY if fake_mode() and DEFAULT_DELAY == (2.0, 6.0) else DEFAULT_DELAY


# Swapped by tests and by JOBFINDER_FAKE_SOURCES=1 (replays fixtures; see sources/fake.py).
_transport_factory: Callable[[], httpx.BaseTransport] | None = None


def set_transport_factory(factory: Callable[[], httpx.BaseTransport] | None) -> None:
    global _transport_factory
    _transport_factory = factory


def fake_mode() -> bool:
    return os.environ.get("JOBFINDER_FAKE_SOURCES") == "1"


class PoliteClient:
    def __init__(self, delay: tuple[float, float] | None = None, sleep: Callable[[float], None] = time.sleep,
                 timeout: float = 20.0, wait_first: bool = False):
        transport = _transport_factory() if _transport_factory else None
        if transport is None and fake_mode():
            from sources.fake import fake_transport
            transport = fake_transport()
        self._client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True,
                                    headers={"User-Agent": USER_AGENT, "Accept-Language": "en-MY,en;q=0.9"})
        self.delay = delay if delay is not None else current_delay()
        self._sleep = sleep
        self._first = not wait_first  # wait_first: another client just hit the same site
        self.requests_made = 0

    def _pause(self) -> None:
        if not self._first and self.delay[1] > 0:
            self._sleep(random.uniform(*self.delay))
        self._first = False

    def request(self, method: str, url: str, **kw) -> httpx.Response:
        self._pause()
        try:
            r = self._client.request(method, url, **kw)
        except httpx.HTTPError as e:
            log_request(method, str(httpx.URL(url, params=kw.get("params"))), e.__class__.__name__)
            raise SourceError(f"{e.__class__.__name__} contacting {httpx.URL(url).host}") from e
        finally:
            self.requests_made += 1
        hops = "".join(f" {h.status_code}->{h.headers.get('location', '')}" for h in r.history)
        log_request(method, str(r.request.url), f"{r.status_code}{hops}")
        if r.status_code in BLOCK_STATUSES:
            raise RateLimited(r.status_code, str(r.url), save_response(r, "blocked"))
        if r.status_code >= 400:
            saved = save_response(r, "error status")
            raise SourceError(f"HTTP {r.status_code} from {r.url.host} (response saved to {saved})")
        return r

    def get_json(self, url: str, **kw) -> dict:
        r = self.request("GET", url, **kw)
        try:
            return r.json()
        except ValueError as e:
            raise SchemaChanged(f"{r.url.host} did not return JSON (saved to {save_response(r, 'not JSON')})") from e

    def post_json(self, url: str, payload: dict, **kw) -> dict:
        r = self.request("POST", url, json=payload, **kw)
        try:
            return r.json()
        except ValueError as e:
            raise SchemaChanged(f"{r.url.host} did not return JSON (saved to {save_response(r, 'not JSON')})") from e

    def close(self) -> None:
        self._client.close()
