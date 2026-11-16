"""After the 13 Nov smoke test (HTTP 403 from my.jobstreet.com, nothing saved): every block / error response is
saved locally, every request is logged, cards in hand survive a block, and a small cap means one search.
All mocked. No network."""
import json
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session, select

from models import Job, SearchProfile
from sources.fake import jobstreet_handler
from sources.http import BODY_PREVIEW, PoliteClient, RateLimited, SourceError, set_transport_factory
from sources.jobstreet import PAGE_SIZE, JobStreetSource

NO_SLEEP = lambda s: None  # noqa: E731
CHALLENGE = "<html><head><title>Just a moment...</title></head><body>" + "x" * 5000 + "</body></html>"


def debug_files(prefix: str = "") -> list[Path]:
    from app.config import DATA_DIR
    d = DATA_DIR / "debug"
    return sorted(d.glob(f"{prefix}*.json")) if d.exists() else []


def request_log() -> list[str]:
    from app.config import DATA_DIR
    f = DATA_DIR / "logs" / "requests.log"
    return f.read_text(encoding="utf-8").splitlines() if f.exists() else []


@pytest.fixture(autouse=True)
def clean_diagnostics():
    for f in debug_files():
        f.unlink()
    from app.config import DATA_DIR
    (DATA_DIR / "logs" / "requests.log").unlink(missing_ok=True)


@pytest.fixture
def net():
    seen: list[httpx.Request] = []
    overrides: dict = {}

    def handler(r):
        seen.append(r)
        return jobstreet_handler(r, overrides)

    set_transport_factory(lambda: httpx.MockTransport(handler))
    yield seen, overrides
    set_transport_factory(None)


# ---------- PoliteClient saves what the site answered ----------

@pytest.mark.parametrize("status", [403, 429, 999])
def test_block_response_is_saved(net, status):
    _, overrides = net
    overrides["/job/"] = httpx.Response(status, text=CHALLENGE, headers={
        "server": "cloudflare", "cf-ray": "8abc123-SIN", "content-type": "text/html", "set-cookie": "__cf_bm=secret"})
    with pytest.raises(RateLimited) as exc:
        PoliteClient(sleep=NO_SLEEP).request("GET", "https://my.jobstreet.com/job/1")
    [f] = debug_files(f"response-my.jobstreet.com-{status}")
    assert exc.value.saved == str(f) and str(f) in str(exc.value)
    d = json.loads(f.read_text(encoding="utf-8"))
    assert (d["method"], d["url"], d["status"], d["why"]) == ("GET", "https://my.jobstreet.com/job/1", status, "blocked")
    assert d["response_headers"]["server"] == "cloudflare" and d["response_headers"]["cf-ray"] == "8abc123-SIN"
    assert d["response_headers"]["set-cookie"] == "<redacted>"  # site cookies are not kept
    assert "JobFinder" in d["request_headers"]["user-agent"]
    body = d[f"body_first_{BODY_PREVIEW}_bytes"]
    assert body.startswith("<html><head><title>Just a moment") and len(body) == BODY_PREVIEW
    assert d["body_bytes"] == len(CHALLENGE)


def test_other_error_responses_and_non_json_are_saved_too(net):
    _, overrides = net
    overrides["/graphql"] = httpx.Response(400, json={"errors": [{"message": "Cannot query field"}]})
    client = PoliteClient(sleep=NO_SLEEP)
    with pytest.raises(SourceError, match="response saved to"):
        client.post_json("https://my.jobstreet.com/graphql", {})
    [f] = debug_files("response-my.jobstreet.com-400")
    assert "Cannot query field" in json.loads(f.read_text(encoding="utf-8"))[f"body_first_{BODY_PREVIEW}_bytes"]
    overrides["/api/jobsearch"] = httpx.Response(200, text="<html>not json</html>")
    with pytest.raises(SourceError, match="did not return JSON .saved to"):
        client.get_json("https://my.jobstreet.com/api/jobsearch/v5/search")
    assert debug_files("response-my.jobstreet.com-200")


def test_every_request_is_logged_in_order(net):
    _, overrides = net
    overrides["/job/"] = httpx.Response(403)
    client = PoliteClient(sleep=NO_SLEEP)
    client.get_json("https://my.jobstreet.com/api/jobsearch/v5/search", params={"keywords": "software engineer"})
    with pytest.raises(RateLimited):
        client.request("GET", "https://my.jobstreet.com/job/1")
    log = request_log()
    assert len(log) == 2
    assert "GET https://my.jobstreet.com/api/jobsearch/v5/search?keywords=software+engineer -> 200" in log[0]
    assert log[1].endswith("GET https://my.jobstreet.com/job/1 -> 403")


# ---------- JobStreet details: GraphQL only, never the job web page (#102) ----------

def prof(**kw):
    base = dict(name="Smoke test", keywords=["software engineer"], locations=["Kuala Lumpur"], job_type="fulltime", days=0)
    base.update(kw)
    return SearchProfile(**base)


def test_graphql_error_keeps_summaries_and_never_requests_the_job_page(net):
    """The 13 Nov shape minus the page fallback: GraphQL fails once -> no more detail requests, all cards kept."""
    seen, overrides = net
    overrides["/graphql"] = httpx.Response(400, json={"errors": [{"message": "bad query"}]})
    src = JobStreetSource(PoliteClient(sleep=NO_SLEEP), max_results=5)
    jobs = src.fetch(prof())
    assert [(r.method, r.url.path) for r in seen] == [("GET", "/api/jobsearch/v5/search"), ("POST", "/graphql")]
    assert len(jobs) == 3 and all("Summary only" in j.description for j in jobs)
    assert sum("GraphQL failed" in n for n in src.notes) == 1
    assert debug_files("response-my.jobstreet.com-400")


def test_graphql_block_keeps_summaries_and_pauses(client, net):
    seen, overrides = net
    overrides["/graphql"] = httpx.Response(403, text=CHALLENGE, headers={"server": "cloudflare"})
    from app.db import engine
    from sources.runner import run_fetch
    with Session(engine) as s:
        smoke = prof()
        s.add(smoke)
        s.commit()
        [res] = run_fetch(s, source_keys=["jobstreet"], profile_ids=[smoke.id], results_cap=5, sleep=NO_SLEEP)
        assert res.status == "paused" and "HTTP 403" in res.message
        assert res.fetched == 3 and res.requests == 2  # 1 search + 1 details request, then stop
        assert "saved 3 job(s) from their search summary" in res.message
        assert len(s.exec(select(Job)).all()) == 3
    assert not any(r.url.path.startswith("/job/") for r in seen)
    assert debug_files("response-my.jobstreet.com-403")


def test_smoke_shape_is_two_requests_on_success(net):
    """Tomorrow's check (cap 1): 1 search + 1 details request."""
    seen, _ = net
    jobs = JobStreetSource(PoliteClient(sleep=NO_SLEEP), max_results=1).fetch(prof())
    assert len(jobs) == 1 and "Summary only" not in jobs[0].description
    assert [r.url.path for r in seen] == ["/api/jobsearch/v5/search", "/graphql"]


# ---------- paging: a small cap means one search per query ----------

def test_small_cap_never_pages_past_page_one(net):
    seen, overrides = net
    full_page = {"data": [{"id": str(100 + i), "title": f"Dev {i}", "workTypes": ["Contract"]} for i in range(PAGE_SIZE)]}
    full_page["data"][:2] = [{"id": "1", "title": "A", "workTypes": ["Full time"]},
                             {"id": "2", "title": "B", "workTypes": ["Full time"]}]
    overrides["/api/jobsearch"] = httpx.Response(200, json=full_page)  # 28 of 30 filtered out (not full time)
    overrides["/graphql"] = httpx.Response(500)
    JobStreetSource(PoliteClient(sleep=NO_SLEEP), max_results=5).fetch(prof())
    searches = [r for r in seen if r.url.path == "/api/jobsearch/v5/search"]
    assert len(searches) == 1 and searches[0].url.params["pageSize"] == str(PAGE_SIZE)


def test_cap_above_a_page_may_use_page_two(net):
    seen, overrides = net
    page = {"data": [{"id": str(i), "title": f"Dev {i}", "workTypes": ["Contract"]} for i in range(PAGE_SIZE)]}
    overrides["/api/jobsearch"] = httpx.Response(200, json=page)
    JobStreetSource(PoliteClient(sleep=NO_SLEEP), max_results=50).fetch(prof())
    assert [r.url.params["page"] for r in seen] == ["1", "2"]
