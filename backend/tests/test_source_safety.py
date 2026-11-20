"""Polite HTTP client + source health rules. No network: httpx.MockTransport only."""
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from models import Source
from sources import health
from sources.http import USER_AGENT, PoliteClient, RateLimited, SchemaChanged, SourceError, set_transport_factory

NOW = datetime(2026, 11, 8, 9, 0, tzinfo=UTC)


@pytest.fixture
def transport():
    seen: list[httpx.Request] = []
    responses: dict[str, httpx.Response] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses.get(request.url.path, httpx.Response(200, json={"ok": True}))

    set_transport_factory(lambda: httpx.MockTransport(handler))
    yield seen, responses
    set_transport_factory(None)


def test_client_is_polite_and_honest(transport):
    seen, _ = transport
    pauses = []
    c = PoliteClient(delay=(2, 6), sleep=pauses.append)
    for _ in range(3):
        assert c.get_json("https://example.test/a") == {"ok": True}
    assert len(seen) == 3 and c.requests_made == 3
    assert len(pauses) == 2 and all(2 <= p <= 6 for p in pauses)  # no pause before the first request
    ua = seen[0].headers["user-agent"]
    assert ua == USER_AGENT and "JobFinder" in ua and "Mozilla/5.0" in ua
    assert "cookie" not in seen[1].headers and "authorization" not in seen[0].headers


@pytest.mark.parametrize("status", [403, 429])
def test_403_429_raise_rate_limited(transport, status):
    _, responses = transport
    responses["/blocked"] = httpx.Response(status)
    with pytest.raises(RateLimited) as e:
        PoliteClient(sleep=lambda s: None).get_json("https://example.test/blocked")
    assert e.value.status == status


def test_other_errors(transport):
    _, responses = transport
    responses["/500"] = httpx.Response(500)
    responses["/html"] = httpx.Response(200, text="<html>")
    c = PoliteClient(sleep=lambda s: None)
    with pytest.raises(SourceError):
        c.get_json("https://example.test/500")
    with pytest.raises(SchemaChanged):
        c.get_json("https://example.test/html")


def test_daily_limit_and_rollover():
    src = Source(key="linkedin", max_runs_per_day=1)
    assert health.can_run(src, NOW) == (True, "")
    health.record_run(src, NOW)
    ok, why = health.can_run(src, NOW + timedelta(hours=3))
    assert not ok and "daily limit" in why
    assert health.can_run(src, NOW + timedelta(days=1))[0]  # new day


def test_rate_limit_pauses_24h_and_notifies(client):
    from sqlmodel import Session, select

    from app.db import engine
    from models import Notification
    with Session(engine) as s:
        src = s.get(Source, "jobstreet")
        health.record_failure(s, src, RateLimited(429, "https://my.jobstreet.com/api"), NOW)
        s.commit()
        assert src.status == "paused" and src.paused_until == NOW + timedelta(hours=24)
        assert "429" in src.last_error
        ok, why = health.can_run(src, NOW + timedelta(hours=23))
        assert not ok and "paused until" in why
        assert health.can_run(src, NOW + timedelta(hours=24, minutes=1))[0]  # pause lifts by itself
        n = s.exec(select(Notification).where(Notification.type == "source_paused")).all()
        assert len(n) == 1 and "JobStreet paused for 24 hours" in n[0].message


def test_three_consecutive_errors_pause(client):
    from sqlmodel import Session

    from app.db import engine
    with Session(engine) as s:
        src = s.get(Source, "indeed")
        for _ in range(2):
            health.record_failure(s, src, SourceError("timeout"), NOW)
            assert src.status == "error"
        health.record_failure(s, src, SourceError("timeout"), NOW)
        assert src.status == "paused" and "3 errors in a row" in src.last_error
        health.resume(src)
        assert src.status == "ok" and src.paused_until is None


def test_success_resets_error_count():
    src = Source(key="indeed", consecutive_errors=2, status="error")
    health.record_success(src, "5 jobs")
    assert (src.status, src.consecutive_errors, src.last_result) == ("ok", 0, "5 jobs")


def test_defaults_seeded(client):
    from sqlmodel import Session, select

    from app.db import engine
    from models import SearchProfile
    with Session(engine) as s:
        assert (s.get(Source, "linkedin").max_results, s.get(Source, "linkedin").max_runs_per_day) == (15, 1)
        assert s.get(Source, "glassdoor").enabled is False
        profiles = {p.name: p for p in s.exec(select(SearchProfile)).all()}
        assert profiles["KL/Selangor"].locations == ["Kuala Lumpur", "Selangor", "Remote"]
        assert profiles["Sabah"].keywords == health.DEFAULT_KEYWORDS and profiles["Sabah"].days == 7


def test_limits_are_clamped():
    src = Source(key="linkedin", max_results=500, max_runs_per_day=9)
    health.clamp_limits(src)
    assert (src.max_results, src.max_runs_per_day) == (30, 2)
