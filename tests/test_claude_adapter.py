"""TEST_PLAN.md cases 25, 36, 37: the Claude adapter translates both ways. No network."""
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.models import claude
from app.models.base import (Message, ModelError, ModelNotConfigured, ToolCall,
                             ToolResult, ToolSpec)

HISTORY = [
    Message(role="user", text="Investigate run r1."),
    Message(role="assistant", text="Looking.",
            tool_calls=[ToolCall(id="toolu_1", name="get_event", input={"event_id": 6})]),
    Message(role="user", tool_results=[ToolResult(call_id="toolu_1", content="no event 6",
                                                  is_error=True)]),
]

def test_case25_history_becomes_claude_messages():
    out = [claude.to_claude_message(m) for m in HISTORY]
    assert out[0] == {"role": "user", "content": [{"type": "text", "text": "Investigate run r1."}]}
    assert out[1]["content"] == [
        {"type": "text", "text": "Looking."},
        {"type": "tool_use", "id": "toolu_1", "name": "get_event", "input": {"event_id": 6}}]
    assert out[2]["content"] == [{"type": "tool_result", "tool_use_id": "toolu_1",
                                  "content": "no event 6", "is_error": True}]

def test_case25_empty_reply_is_never_an_empty_message():
    assert claude.to_claude_message(Message(role="assistant"))["content"] == [
        {"type": "text", "text": "(empty)"}]

def test_case25_tools_use_input_schema():
    t = ToolSpec(name="get_run", description="d", parameters={"type": "object"})
    assert claude.to_claude_tool(t) == {"name": "get_run", "description": "d",
                                        "input_schema": {"type": "object"}}

def test_case25_claude_reply_becomes_model_reply():
    response = SimpleNamespace(stop_reason="tool_use", content=[
        SimpleNamespace(type="text", text="Let me look "),
        SimpleNamespace(type="text", text="at the last reply."),
        SimpleNamespace(type="tool_use", id="toolu_2", name="get_event", input={"event_id": 6})])
    reply = claude.from_claude(response)
    assert reply.text == "Let me look at the last reply."
    assert reply.tool_calls == [ToolCall(id="toolu_2", name="get_event", input={"event_id": 6})]
    assert reply.cut_off is False

def _recording_client(sent):
    def create(**kw):
        sent.update(kw)
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text="{}")])
    return SimpleNamespace(messages=SimpleNamespace(create=create))

def test_case25_next_sends_the_translated_request():
    sent = {}
    tool = ToolSpec(name="get_event", description="d", parameters={"type": "object"})
    reply = claude.ClaudeModel("claude-x", client=_recording_client(sent)).next(
        "be careful", [tool], HISTORY, timeout=180)
    assert reply.text == "{}" and reply.tool_calls == []
    assert sent["model"] == "claude-x" and sent["system"] == "be careful"
    assert sent["tools"] == [claude.to_claude_tool(tool)]
    assert sent["messages"] == [claude.to_claude_message(m) for m in HISTORY]
    assert sent["messages"][1]["content"][1]["type"] == "tool_use"

# Case 36

def test_case36_each_try_gets_a_third_of_the_budget():
    sent = {}
    claude.ClaudeModel("claude-x", client=_recording_client(sent)).next(
        "", [], HISTORY, timeout=180)
    # 1 try + 2 retries, so 3 × 60 s fits in the 180 s budget.
    assert claude.RETRIES == 2 and sent["timeout"] == 60

# Case 37

def test_case37_max_tokens_means_cut_off():
    def response(stop_reason):
        return SimpleNamespace(stop_reason=stop_reason,
                               content=[SimpleNamespace(type="text", text='{"outcome": "succ')])
    assert claude.from_claude(response("max_tokens")).cut_off is True
    assert claude.from_claude(response("end_turn")).cut_off is False

def test_case25_no_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ModelNotConfigured, match="ANTHROPIC_API_KEY"):
        claude.ClaudeModel("claude-x")

def test_case25_api_error_becomes_model_error():
    def create(**kw):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api"))
    fake = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(ModelError, match="model call failed"):
        claude.ClaudeModel("claude-x", client=fake).next("", [], HISTORY, timeout=180)
