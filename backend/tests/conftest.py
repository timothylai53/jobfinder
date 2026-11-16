import os
import shutil
import tempfile

# Point the app at a throwaway data dir before any app module is imported.
_TMP = tempfile.mkdtemp(prefix="jobfinder-test-")
os.environ["JOBFINDER_DATA_DIR"] = _TMP
os.environ["JOBFINDER_NO_SCHEDULER"] = "1"  # tests drive automations directly
os.environ["JOBFINDER_TEMPLATES_DIR"] = os.path.join(_TMP, "prompt-templates")  # edited prompts never touch the repo

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402


@pytest.fixture
def client():
    from app.db import engine
    from app.main import app

    SQLModel.metadata.drop_all(engine)
    with TestClient(app) as c:  # runs lifespan: create tables + seed
        yield c


def pytest_sessionfinish(session, exitstatus):
    from app.db import engine

    engine.dispose()
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def no_fake_sources_env(monkeypatch):
    """Same result whatever the shell or CI sets: JOBFINDER_FAKE_SOURCES=1 would switch to the fake-mode delay and
    fake JobSpy, so it is cleared for every test. A test that needs fake mode sets it itself (monkeypatch.setenv)."""
    monkeypatch.delenv("JOBFINDER_FAKE_SOURCES", raising=False)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never reach a real site: real HTTP transports and the real JobSpy call fail loudly."""
    import httpx

    def blocked(self, request):
        raise RuntimeError(f"network disabled in tests: {request.method} {request.url}")

    def blocked_scrape(**kw):
        raise RuntimeError("network disabled in tests: jobspy.scrape_jobs")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr("sources.jobspy_source.real_scrape", blocked_scrape)
