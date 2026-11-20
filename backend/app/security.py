"""Local-only protections for the API (see SECURITY.md).

The API listens on 127.0.0.1, but any web page open in the same browser can still try to talk to it:
- DNS rebinding: a hostile site makes its own domain resolve to 127.0.0.1 and reads the API as "same origin".
  Defence: only Host headers naming this machine are accepted.
- CSRF: a hostile site submits a form or fetch() to http://127.0.0.1:8730/api/... (the browser sends it even though
  the site can't read the answer). Defence: state-changing requests must come from the local frontend's origin,
  or carry no Origin at all (scripts, curl, tests); cross-site Sec-Fetch-Site is refused.
- CORS is limited to the local frontend, so other origins can't read responses either.
"""
import os
import re

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
_DEFAULT_ORIGINS = "http://localhost:5730,http://127.0.0.1:5730"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def frontend_origins() -> set[str]:
    """The local frontend's origins. JOBFINDER_FRONTEND_ORIGINS adds others (the screenshot script uses port 5731)."""
    extra = os.environ.get("JOBFINDER_FRONTEND_ORIGINS", "")
    return {o.strip().rstrip("/") for o in f"{_DEFAULT_ORIGINS},{extra}".split(",") if o.strip()}


def _host_name(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("["):  # [::1]:8730
        return host[: host.find("]") + 1]
    return host.rsplit(":", 1)[0] if re.fullmatch(r"[^:]+:\d+", host) else host


class LocalOnlyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.origins = frontend_origins()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        if _host_name(headers.get("host", "")) not in ALLOWED_HOSTS | {"[::1]"}:
            await PlainTextResponse("Invalid Host header: JobFinder only answers on 127.0.0.1 / localhost.", 400)(scope, receive, send)
            return
        if scope["method"] not in SAFE_METHODS:
            origin = headers.get("origin", "").rstrip("/")
            if (origin and origin not in self.origins) or headers.get("sec-fetch-site") == "cross-site":
                await PlainTextResponse("Cross-site request refused.", 403)(scope, receive, send)
                return

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                h = list(message.get("headers", []))
                present = {k.lower() for k, _ in h}
                for k, v in ((b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
                             (b"referrer-policy", b"no-referrer")):
                    if k not in present:
                        h.append((k, v))
                message["headers"] = h
            await send(message)

        await self.app(scope, receive, with_headers)


def install(app) -> None:
    """CORS for the local frontend only, then the Host / Origin checks (outermost)."""
    app.add_middleware(CORSMiddleware, allow_origins=sorted(frontend_origins()), allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(LocalOnlyMiddleware)
