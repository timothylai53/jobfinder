"""Tolerant parser + schema validation (brief §6.6, §9: tests for the tolerant parser). Pure, no DB."""
import json
from pathlib import Path

import pytest

from ai.parser import ReplyError, decode, extract_json_text, parse_reply
from ai.schemas import EXAMPLES, SCHEMAS

FIX = Path(__file__).parent / "fixtures" / "ai"


def reply(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("task", list(SCHEMAS))
def test_every_prompt_example_matches_its_schema(task):
    SCHEMAS[task].model_validate(json.loads(EXAMPLES[task]))


def test_json_code_block_with_chatter_around_it():
    out = parse_reply("tailor_resume", reply("tailor_valid.txt"))
    assert out.ok and out.repairs == []
    assert [s["section"] for s in out.data["sections"]] == ["Experience", "Projects", "Education", "Certifications", "Publications"]


def test_broken_json_is_repaired():
    out = parse_reply("tailor_resume", reply("tailor_broken_json.txt"))
    assert out.ok, out.errors
    assert set(out.repairs) == {"replaced smart quotes", "removed trailing commas"}
    assert out.data["summary"] == "Graduate developer with Python and SQL experience."
    assert out.data["omitted_ids"] == ["B5"]


def test_schema_errors_name_the_exact_field():
    out = parse_reply("tailor_resume", reply("tailor_schema_error.txt"))
    assert not out.ok and out.raw is not None
    paths = {e["path"] for e in out.errors}
    assert "skills_order" in paths  # a string instead of a list
    assert "sections.0.items.0.text" in paths  # missing text


@pytest.mark.parametrize("text,expected", [
    ('```json\n{"a": 1}\n```', '{"a": 1}'),
    ('```\n{"a": {"b": "}"}}\n```', '{"a": {"b": "}"}}'),  # a brace inside a string
    ('Text before {"a": [1, 2]} text after', '{"a": [1, 2]}'),
    ('```python\nx = 1\n```\n```json\n{"a": 1}\n```', '{"a": 1}'),  # the json block wins
])
def test_extraction(text, expected):
    assert extract_json_text(text) == expected


def test_python_literals_and_comments_repaired():
    obj, repairs = decode('{\n  "ok": True, // yes\n  "none": None,\n  "url": "https://example.com"\n}')
    assert obj == {"ok": True, "none": None, "url": "https://example.com"}  # a URL is not a comment
    assert "removed // comments" in repairs and "converted True/False/None" in repairs


@pytest.mark.parametrize("text,message", [
    ("", "empty"),
    ("I can't help with that.", "No JSON object"),
    ('```json\n{"a": 1, "b": }\n```', "broken at line"),
    ('```json\n{"a": "unterminated\n```', "No JSON object"),
])
def test_unusable_replies_explain_why(text, message):
    with pytest.raises(ReplyError, match=message):
        decode(text)


def test_reply_error_becomes_a_reported_error():
    out = parse_reply("cover_letter", "no json here")
    assert not out.ok and out.errors[0]["path"] == "(reply)" and "No JSON object" in out.errors[0]["message"]


def test_wrong_enum_and_range_reported():
    bad = '{"requirements": [{"text": "x", "type": "must", "status": "met"}], "overall_fit": 140}'
    paths = {e["path"] for e in parse_reply("deep_analysis", bad).errors}
    assert paths == {"requirements.0.type", "overall_fit"}
