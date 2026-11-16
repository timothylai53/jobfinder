"""Ollama provider: the same prompts, sent to the LOCAL Ollama API (http://localhost:11434). Nothing else.

Clear messages for the usual problems: Ollama not running, model not installed, too slow (timeout).
Tests swap the transport (set_transport_factory); the real client only ever talks to localhost.
"""
import os
from collections.abc import Callable

import httpx

OLLAMA_URL = os.environ.get("JOBFINDER_OLLAMA_URL", "http://127.0.0.1:11434")  # Ollama's default; 127.0.0.1 avoids a slow IPv6 attempt on Windows

NOT_RUNNING = ("Ollama is not running. Install it from ollama.com and start it (it runs in the background), "
               "or switch AI mode to Copy-Paste in Settings.")


class OllamaError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind  # not_running / model_missing / timeout / error


_transport_factory: Callable[[], httpx.BaseTransport] | None = None


def set_transport_factory(factory: Callable[[], httpx.BaseTransport] | None) -> None:
    global _transport_factory
    _transport_factory = factory


def _client(timeout: float) -> httpx.Client:
    transport = _transport_factory() if _transport_factory else None
    return httpx.Client(base_url=OLLAMA_URL, transport=transport, timeout=httpx.Timeout(timeout, connect=3.0))


def _installed(name: str, models: list[str]) -> bool:
    want = name if ":" in name else f"{name}:latest"
    return want in models or name in models


def status(model: str) -> dict:
    """{'running', 'models', 'model', 'installed', 'message'} for the Settings page and before every run."""
    try:
        with _client(5) as c:
            r = c.get("/api/tags")
            r.raise_for_status()
            models = [m.get("name", "") for m in r.json().get("models", [])]
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return {"running": False, "models": [], "model": model, "installed": False, "message": NOT_RUNNING}
    except (httpx.HTTPError, ValueError) as e:
        return {"running": False, "models": [], "model": model, "installed": False,
                "message": f"Ollama answered unexpectedly ({e.__class__.__name__}). Is something else using port 11434?"}
    installed = _installed(model, models)
    message = "Ready." if installed else f"Model {model} is not installed. Open a terminal and run: ollama pull {model}"
    return {"running": True, "models": models, "model": model, "installed": installed, "message": message}


def generate(prompt: str, model: str, timeout_s: float) -> str:
    """One chat turn. Returns the model's reply text. Raises OllamaError with a user-facing message."""
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False,
            "format": "json", "options": {"temperature": 0.2, "num_ctx": 8192}}
    try:
        with _client(timeout_s) as c:
            r = c.post("/api/chat", json=body)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise OllamaError("not_running", NOT_RUNNING) from e
    except httpx.TimeoutException as e:
        raise OllamaError("timeout", f"Ollama took longer than {timeout_s:g} s. Try a smaller model, or raise the "
                                     "timeout in Settings.") from e
    except httpx.HTTPError as e:
        raise OllamaError("error", f"Could not talk to Ollama ({e.__class__.__name__}).") from e
    if r.status_code == 404:
        raise OllamaError("model_missing", f"Model {model} is not installed. Open a terminal and run: ollama pull {model}")
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("error", "")
        except ValueError:
            pass
        raise OllamaError("error", f"Ollama returned HTTP {r.status_code}{': ' + detail if detail else ''}.")
    try:
        return r.json()["message"]["content"]
    except (ValueError, KeyError, TypeError) as e:
        raise OllamaError("error", "Ollama's answer had no message in it.") from e
