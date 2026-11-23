"""Copy-Paste keeps working: each saved fake reply (what a web chat answered) parses, validates and gets the expected
guard result through the current prompts, and the example JSON every prompt shows is itself a valid reply shape."""
import pytest

from ai import prompts
from ai.parser import extract_json_text, parse_reply
from tests.test_ai_flow import fx, new_task, setup  # noqa: F401 (fixture)


@pytest.mark.parametrize("task", ("deep_analysis", "tailor_resume", "cover_letter", "interview_prep", "parse_resume"))
def test_the_example_in_every_prompt_is_a_valid_reply_shape(task):
    example = "```json\n" + extract_json_text(prompts.schema_text(task)) + "\n```"
    out = parse_reply(task, example)
    assert out.errors == [], out.errors  # schema-valid; its "..." values are what the placeholder flag is for


@pytest.mark.parametrize(("task", "reply", "flags"), [
    ("tailor_resume", "tailor_valid.txt", []),
    ("deep_analysis", "deep_analysis_valid.txt", None),
    ("interview_prep", "interview_prep_valid.txt", None),
    ("cover_letter", "cover_letter_valid.txt", None),
])
def test_saved_copy_paste_replies_still_parse_with_the_current_prompts(setup, task, reply, flags):  # noqa: F811
    client, job_id = setup
    t = new_task(client, job_id, task)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx(reply)}).json()
    assert t["status"] == "parsed" and t["errors"] == []
    if flags is not None:
        assert t["flags"] == flags


def test_a_chat_that_adds_a_sentence_before_the_json_still_parses(setup):  # noqa: F811
    """Web chats often say something before the JSON despite being told not to: the reply must still work."""
    client, job_id = setup
    t = new_task(client, job_id)
    reply = "Here is the tailored resume, using only your bank items.\n\n" + fx("tailor_valid.txt")
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": reply}).json()
    assert t["status"] == "parsed" and t["flags"] == []
