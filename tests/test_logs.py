"""TEST_PLAN.md cases 48 and 50: the investigation log."""
import json
import logging

from app import config, investigator, logs
from app.models.base import ModelError
from tests.conftest import REPORT, FakeModel, ask, say, submit

SECRET = "the run's private words"


def _with_usage(reply, n_in, n_out, cost, thinking=SECRET):
    return reply.model_copy(update={"in_tokens": n_in, "out_tokens": n_out,
                                    "cost": cost, "thinking": thinking})


def _lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name.startswith("app")]


# Case 48

def test_case48_info_log_tells_the_story(viewer, caplog):
    caplog.set_level(level=logging.INFO, logger="app")
    model = FakeModel(_with_usage(reply=ask(name="get_run"), n_in=1000, n_out=20, cost=0.001),
                      _with_usage(reply=submit(report=REPORT), n_in=3000, n_out=200, cost=0.002))
    investigator.investigate(client=viewer, model=model, run_id="ok")
    lines = _lines(caplog=caplog)
    assert all(line.startswith("[ok] ") for line in lines)
    assert "start  fake-model  6 events" in lines[0]
    assert "call 1" in lines[1] and "in 1,000 / out 20" in lines[1] and "→ get_run()" in lines[1]
    assert "tool get_run()  ok" in lines[2] and "chars" in lines[2]
    assert "call 2" in lines[3] and "$0.0020" in lines[3] and "→ submit_report" in lines[3]
    assert lines[4].startswith("[ok] done  2 calls")
    assert "in 4,000 / out 220" in lines[4] and "$0.0030" in lines[4]
    assert len(lines) == 5
    assert not any(SECRET in line or "family_search" in line for line in lines)


def test_case48_debug_adds_thinking_and_words(viewer, caplog):
    caplog.set_level(level=logging.DEBUG, logger="app")
    model = FakeModel(_with_usage(reply=ask(name="get_run", text="Let me look."), n_in=1, n_out=1, cost=0.0),
                      submit(report=REPORT))
    investigator.investigate(client=viewer, model=model, run_id="ok")
    lines = _lines(caplog=caplog)
    assert any(f"thinking: {SECRET}" in line for line in lines)
    assert any("says: Let me look." in line for line in lines)


def test_case48_unknown_tokens_and_cost_show_question_marks(viewer, caplog):
    caplog.set_level(level=logging.INFO, logger="app")
    # The 1st reply has a cost, the 2nd doesn't: the total must not pretend.
    model = FakeModel(_with_usage(reply=ask(name="get_run"), n_in=10, n_out=1, cost=0.5), submit(report=REPORT))
    investigator.investigate(client=viewer, model=model, run_id="ok")
    lines = _lines(caplog=caplog)
    assert "in ? / out ?  $?" in lines[3]
    assert "in ? / out ?  $?" in lines[-1]


# Case 50

def test_case50_rejected_report_cut_off_and_tool_error(viewer, caplog):
    caplog.set_level(level=logging.INFO, logger="app")
    model = FakeModel(ask(name="get_event", event_id=99),
                      say(text='{"outcome": "succ', cut_off=True),
                      say(text="It looks fine."),
                      submit(report=REPORT))
    investigator.investigate(client=viewer, model=model, run_id="ok")
    text = "\n".join(_lines(caplog=caplog))
    assert "tool get_event(event_id=99)  error: " in text and "no event 99" in text
    assert "→ cut off" in text
    assert "report rejected: Your answer has no tool call." in text


# Case 56

def test_case56_report_content_stays_out_of_the_info_log(viewer, caplog):
    caplog.set_level(level=logging.INFO, logger="app")
    marked = {**REPORT, "summary": SECRET}
    no_step = {k: v for k, v in marked.items() if k != "next_step"}
    model = FakeModel(submit(report=no_step), submit(report=marked))
    investigator.investigate(client=viewer, model=model, run_id="ok")
    lines = _lines(caplog=caplog)
    assert "→ submit_report" in lines[1] and "report rejected: " in lines[2]
    assert "next_step" in lines[2]
    assert not any(SECRET in line for line in lines)


def test_case50_step_limit_and_model_error(viewer, caplog):
    caplog.set_level(level=logging.INFO, logger="app")
    investigator.investigate(client=viewer, model=FakeModel(ask(name="get_run")), run_id="ok")
    assert f"stopped: step limit ({config.MAX_STEPS} model calls)" in _lines(caplog=caplog)[-1]
    investigator.investigate(client=viewer, model=FakeModel(ModelError("model call failed: overloaded")), run_id="ok")
    assert "error: model call failed: overloaded" in _lines(caplog=caplog)[-1]



def test_case50_httpx_request_lines_are_off():
    logs.setup()
    assert logging.getLogger(name="httpx").level == logging.WARNING
