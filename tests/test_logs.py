"""TEST_PLAN.md cases 48 and 50: the investigation log."""
import json
import logging

import httpx
import pytest

from app import config, investigator, logs
from app.adapters import openclaw
from app.models.base import ModelError
from tests.conftest import REPORT, FakeModel, ask, fake_viewer, say

SECRET = "the run's private words"


def _with_usage(reply, n_in, n_out, cost, thinking=SECRET):
    return reply.model_copy(update={"in_tokens": n_in, "out_tokens": n_out,
                                    "cost": cost, "thinking": thinking})


def _lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name.startswith("app")]


# Case 48

def test_case48_info_log_tells_the_story(viewer, caplog):
    caplog.set_level(logging.INFO, logger="app")
    model = FakeModel(_with_usage(ask("get_run"), 1000, 20, 0.001),
                      _with_usage(say(json.dumps(REPORT)), 3000, 200, 0.002))
    investigator.investigate(viewer, model, "ok")
    lines = _lines(caplog)
    assert all(line.startswith("[ok] ") for line in lines)
    assert "start  fake-model  6 events" in lines[0]
    assert "call 1" in lines[1] and "in 1,000 / out 20" in lines[1] and "→ get_run()" in lines[1]
    assert "tool get_run()  ok" in lines[2] and "chars" in lines[2]
    assert "call 2" in lines[3] and "$0.0020" in lines[3] and "→ final answer" in lines[3]
    assert lines[4].startswith("[ok] done  2 calls")
    assert "in 4,000 / out 220" in lines[4] and "$0.0030" in lines[4]
    assert len(lines) == 5
    assert not any(SECRET in line or "family_search" in line for line in lines)


def test_case48_debug_adds_thinking_and_words(viewer, caplog):
    caplog.set_level(logging.DEBUG, logger="app")
    model = FakeModel(_with_usage(ask("get_run", text="Let me look."), 1, 1, 0.0),
                      say(json.dumps(REPORT)))
    investigator.investigate(viewer, model, "ok")
    lines = _lines(caplog)
    assert any(f"thinking: {SECRET}" in line for line in lines)
    assert any("says: Let me look." in line for line in lines)


def test_case48_unknown_tokens_and_cost_show_question_marks(viewer, caplog):
    caplog.set_level(logging.INFO, logger="app")
    # The 1st reply has a cost, the 2nd doesn't: the total must not pretend.
    model = FakeModel(_with_usage(ask("get_run"), 10, 1, 0.5), say(json.dumps(REPORT)))
    investigator.investigate(viewer, model, "ok")
    lines = _lines(caplog)
    assert "in ? / out ?  $?" in lines[3]
    assert "in ? / out ?  $?" in lines[-1]


# Case 50

def test_case50_rejected_report_cut_off_and_tool_error(viewer, caplog):
    caplog.set_level(logging.INFO, logger="app")
    model = FakeModel(ask("get_event", event_id=99),
                      say('{"outcome": "succ', cut_off=True),
                      say("It looks fine."),
                      say(json.dumps(REPORT)))
    investigator.investigate(viewer, model, "ok")
    text = "\n".join(_lines(caplog))
    assert "tool get_event(event_id=99)  error: " in text and "no event 99" in text
    assert "→ cut off" in text
    assert "report rejected: Your final answer has no JSON report." in text


def test_case50_step_limit_and_model_error(viewer, caplog):
    caplog.set_level(logging.INFO, logger="app")
    investigator.investigate(viewer, FakeModel(ask("get_run")), "ok")
    assert f"stopped: step limit ({config.MAX_STEPS} model calls)" in _lines(caplog)[-1]
    investigator.investigate(viewer, FakeModel(ModelError("model call failed: overloaded")), "ok")
    assert "error: model call failed: overloaded" in _lines(caplog)[-1]


def test_case50_viewer_down(caplog):
    caplog.set_level(logging.INFO, logger="app")
    answered = []
    def first_then_refuse(request):
        if answered:
            raise httpx.ConnectError("connection refused", request=request)
        answered.append(1)
        return fake_viewer(request)
    with openclaw.make_client(httpx.MockTransport(first_then_refuse)) as client:
        with pytest.raises(openclaw.ViewerUnavailable):
            investigator.investigate(client, FakeModel(ask("get_run")), "ok")
    assert "viewer down during tool get_run()" in _lines(caplog)[-1]


def test_case50_httpx_request_lines_are_off():
    logs.setup()
    assert logging.getLogger("httpx").level == logging.WARNING
