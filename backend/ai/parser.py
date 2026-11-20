"""Tolerant reply parser, shared by Copy-Paste and Ollama (brief §6.6).

1. Extract the JSON: a ```json code block first, then any ``` block, then the first balanced {...}.
2. Repair common issues: smart quotes, trailing commas, // comments, a BOM, Python True/False/None.
3. Validate against the task's Pydantic schema; every problem is reported with its field path.
"""
import json
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from ai.schemas import SCHEMAS


class ReplyError(Exception):
    """The reply contains no usable JSON object."""


@dataclass
class ParseOutcome:
    ok: bool
    data: dict | None = None  # the validated object (model_dump) when ok
    raw: dict | None = None  # the decoded JSON before validation (for editing)
    errors: list[dict] = field(default_factory=list)  # [{"path": "sections.0.items.1.text", "message": "..."}]
    repairs: list[str] = field(default_factory=list)  # what the parser had to fix


_FENCE = re.compile(r"```(json|JSON)?\s*\n?(.*?)```", re.DOTALL)
_SMART = {"“": '"', "”": '"', "„": '"', "″": '"', "‘": "'", "’": "'", " ": " "}


def _balanced(text: str) -> str | None:
    """The first balanced {...}, skipping braces inside strings."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        start = text.find("{", start + 1)
    return None


def extract_json_text(reply: str) -> str:
    if not reply or not reply.strip():
        raise ReplyError("The reply is empty. Paste the whole reply from the chat.")
    blocks = _FENCE.findall(reply)
    for _lang, body in sorted(blocks, key=lambda b: 0 if b[0] else 1):  # ```json blocks first
        found = _balanced(body)
        if found:
            return found
    found = _balanced(reply)
    if not found:
        raise ReplyError("No JSON object found in the reply. It should contain one ```json code block.")
    return found


def _strip_comments(text: str) -> str:
    """Remove // comments outside strings (a URL like "https://..." inside a value is kept)."""
    out, i, in_str, esc = [], 0, False, False
    while i < len(text):
        ch = text[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _repair(text: str, repairs: list[str]) -> str:
    out = text.lstrip("﻿")
    if any(c in out for c in _SMART):
        for a, b in _SMART.items():
            out = out.replace(a, b)
        repairs.append("replaced smart quotes")
    no_comments = _strip_comments(out)
    if no_comments != out:
        out = no_comments
        repairs.append("removed // comments")
    no_trailing = re.sub(r",(\s*[}\]])", r"\1", out)
    if no_trailing != out:
        out = no_trailing
        repairs.append("removed trailing commas")
    py = re.sub(r"(?<=[:\[,\s])(True|False|None)(?=\s*[,}\]])",
                lambda m: {"True": "true", "False": "false", "None": "null"}[m.group(1)], out)
    if py != out:
        out = py
        repairs.append("converted True/False/None")
    return out


def decode(reply: str) -> tuple[dict, list[str]]:
    """Reply text -> JSON object (+ the repairs made). Raises ReplyError."""
    text = extract_json_text(reply)
    repairs: list[str] = []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        fixed = _repair(text, repairs)
        try:
            obj = json.loads(fixed)
        except json.JSONDecodeError as e:
            line = fixed.splitlines()[e.lineno - 1] if 0 < e.lineno <= len(fixed.splitlines()) else ""
            raise ReplyError(f"The JSON is broken at line {e.lineno}, column {e.colno}: {e.msg}. "
                             f"Line: {line.strip()[:120]}") from e
    if not isinstance(obj, dict):
        raise ReplyError("The reply's JSON is not an object ({...}).")
    return obj, repairs


def _path(loc: tuple) -> str:
    return ".".join(str(p) for p in loc) or "(top level)"


def validate(task: str, obj: dict) -> tuple[BaseModel | None, list[dict]]:
    model = SCHEMAS[task]
    try:
        return model.model_validate(obj), []
    except ValidationError as e:
        return None, [{"path": _path(err["loc"]), "message": err["msg"]} for err in e.errors()]


def parse_reply(task: str, reply: str) -> ParseOutcome:
    try:
        obj, repairs = decode(reply)
    except ReplyError as e:
        return ParseOutcome(ok=False, errors=[{"path": "(reply)", "message": str(e)}])
    model, errors = validate(task, obj)
    if model is None:
        return ParseOutcome(ok=False, raw=obj, errors=errors, repairs=repairs)
    return ParseOutcome(ok=True, data=model.model_dump(), raw=obj, repairs=repairs)
