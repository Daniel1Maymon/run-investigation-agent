"""TEST_PLAN.md cases 46, 47: the OpenRouter adapter. A fake HTTP transport, no network."""
import json

import httpx
import pytest

from app.models import openrouter
from app.models.base import ModelError, ModelNotConfigured, ToolSpec
from tests.test_claude_adapter import HISTORY

TOOL = ToolSpec(name="get_event", description="d", parameters={"type": "object"})


def _reply(content="", tool_calls=None, finish_reason="stop"):
    return {"choices": [{"finish_reason": finish_reason, "message": {
        "role": "assistant", "content": content, "tool_calls": tool_calls}}]}


def _model(monkeypatch, *responses):
    """A model whose HTTP answers come from `responses`, in order. Each is a
    (status, json) pair or an exception to raise. Returns (model, sent requests)."""
    monkeypatch.setenv(name="OPENROUTER_API_KEY", value="sk-test")
    sent, queue = [], list(responses)
    def handler(request):
        sent.append(request)
        r = queue.pop(0)
        if isinstance(r, Exception):
            raise r
        return httpx.Response(status_code=r[0], json=r[1])
    client = httpx.Client(transport=httpx.MockTransport(handler=handler))
    return openrouter.OpenRouterModel(name="vendor/m", client=client, sleep=lambda s: None), sent


# Case 46

def test_case46_history_becomes_openrouter_messages():
    out = [m for h in HISTORY for m in openrouter.to_openrouter_messages(m=h)]
    assert out[0] == {"role": "user", "content": "Investigate run r1."}
    assert out[1] == {"role": "assistant", "content": "Looking.", "tool_calls": [
        {"id": "toolu_1", "type": "function",
         "function": {"name": "get_event", "arguments": '{"event_id": 6}'}}]}
    assert out[2] == {"role": "tool", "tool_call_id": "toolu_1", "content": "Error: no event 6"}
    assert len(out) == 3


def test_case46_empty_reply_is_never_an_empty_message():
    from app.models.base import Message
    assert openrouter.to_openrouter_messages(m=Message(role="assistant")) == [
        {"role": "assistant", "content": "(empty)"}]


def test_case46_tools_are_functions():
    assert openrouter.to_openrouter_tool(tool=TOOL) == {"type": "function", "function": {
        "name": "get_event", "description": "d", "parameters": {"type": "object"}}}


def test_case46_reply_becomes_model_reply():
    reply = openrouter.from_openrouter(data=_reply(content="Let me look.", finish_reason="tool_calls",
        tool_calls=[{"id": "c1", "type": "function",
                     "function": {"name": "get_event", "arguments": '{"event_id": 6}'}}]))
    assert reply.text == "Let me look." and reply.cut_off is False
    assert [(c.id, c.name, c.input) for c in reply.tool_calls] == [
        ("c1", "get_event", {"event_id": 6})]


def test_case46_length_means_cut_off():
    assert openrouter.from_openrouter(data=_reply(content='{"outc', finish_reason="length")).cut_off is True


def test_case46_broken_arguments_become_empty_input():
    reply = openrouter.from_openrouter(data=_reply(tool_calls=[
        {"id": "c1", "type": "function", "function": {"name": "get_event",
                                                      "arguments": '{"event_id": '}}]))
    assert reply.tool_calls[0].input == {}


def test_case46_next_sends_the_translated_request(monkeypatch):
    model, sent = _model(monkeypatch, (200, _reply(content="{}")))
    reply = model.next(instructions="be careful", tools=[TOOL], history=HISTORY, timeout=180)
    assert reply.text == "{}" and reply.tool_calls == []
    body = json.loads(s=sent[0].content)
    assert sent[0].headers["Authorization"] == "Bearer sk-test"
    assert body["model"] == "vendor/m"
    assert body["messages"][0] == {"role": "system", "content": "be careful"}
    assert body["messages"][1:] == [m for h in HISTORY
                                    for m in openrouter.to_openrouter_messages(m=h)]
    assert body["tools"] == [openrouter.to_openrouter_tool(tool=TOOL)]


# Case 47

def test_case47_no_key_is_not_configured(monkeypatch):
    monkeypatch.delenv(name="OPENROUTER_API_KEY", raising=False)
    with pytest.raises(expected_exception=ModelNotConfigured, match="OPENROUTER_API_KEY"):
        openrouter.OpenRouterModel(name="vendor/m")


def test_case47_rate_limit_is_retried(monkeypatch):
    model, sent = _model(monkeypatch, (429, {"error": "slow down"}), (200, _reply(content="{}")))
    assert model.next(instructions="", tools=[], history=HISTORY, timeout=180).text == "{}"
    assert len(sent) == 2


def test_case47_gives_up_after_two_retries(monkeypatch):
    model, sent = _model(monkeypatch, *[(503, {"error": "down"})] * 3)
    with pytest.raises(expected_exception=ModelError, match="503"):
        model.next(instructions="", tools=[], history=HISTORY, timeout=180)
    assert len(sent) == 3


def test_case47_bad_key_is_not_retried(monkeypatch):
    model, sent = _model(monkeypatch, (401, {"error": "bad key"}))
    with pytest.raises(expected_exception=ModelError, match="401"):
        model.next(instructions="", tools=[], history=HISTORY, timeout=180)
    assert len(sent) == 1


def test_case47_error_inside_a_200(monkeypatch):
    model, _ = _model(monkeypatch, (200, {"error": {"code": 502, "message": "provider died"}}))
    with pytest.raises(expected_exception=ModelError, match="provider died"):
        model.next(instructions="", tools=[], history=HISTORY, timeout=180)


def test_case47_timeout_is_retried_then_fails(monkeypatch):
    timeout = httpx.ReadTimeout(message="timed out")
    model, sent = _model(monkeypatch, timeout, timeout, timeout)
    with pytest.raises(expected_exception=ModelError, match="model call failed"):
        model.next(instructions="", tools=[], history=HISTORY, timeout=180)
    assert len(sent) == 3


def test_case47_each_try_gets_a_third_of_the_budget(monkeypatch):
    model, sent = _model(monkeypatch, (200, _reply(content="{}")))
    model.next(instructions="", tools=[], history=HISTORY, timeout=180)
    assert openrouter.RETRIES == 2
    assert sent[0].extensions["timeout"] == {"connect": 60, "read": 60, "write": 60, "pool": 60}


# Case 49

def test_case49_usage_cost_and_thinking(monkeypatch):
    data = _reply(content="{}")
    data["usage"] = {"prompt_tokens": 38, "completion_tokens": 34, "cost": 2.3e-05}
    data["choices"][0]["message"]["reasoning"] = "91 = 7 × 13"
    model, sent = _model(monkeypatch, (200, data))
    reply = model.next(instructions="", tools=[], history=HISTORY, timeout=180)
    assert (reply.in_tokens, reply.out_tokens, reply.cost) == (38, 34, 2.3e-05)
    assert reply.thinking == "91 = 7 × 13"
    assert json.loads(s=sent[0].content)["usage"] == {"include": True}


def test_case49_no_usage_still_works():
    reply = openrouter.from_openrouter(data=_reply(content="{}"))
    assert (reply.in_tokens, reply.out_tokens, reply.cost, reply.thinking) == (None, None, None, "")


# Case 50

def test_case50_retry_is_logged(monkeypatch, caplog):
    import logging
    caplog.set_level(level=logging.INFO, logger="app")
    model, _ = _model(monkeypatch, (429, {"error": "slow down"}), (200, _reply(content="{}")))
    model.next(instructions="", tools=[], history=HISTORY, timeout=180)
    assert "retry 1 after HTTP 429" in caplog.text
