"""TEST_PLAN.md cases 26–32 and 36–45: the agent loop, with a fake model and a fake viewer.
These test our loop, not the model's judgement (that is live case 35)."""
import itertools
import json

import httpx
import pytest

from app import config, investigator, tools
from app.adapters import openclaw
from app.models.base import ModelError
from app.schema import Report
from tests.conftest import REPORT, FakeModel, OK_RUN, ask, ask_many, fake_viewer, say, submit

# Case 26

def test_case26_happy_path(viewer):
    model = FakeModel(ask(name="get_run"), submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    assert inv.status == "done" and inv.model_calls == 2
    assert inv.report.model_dump() == REPORT
    assert [s.tool for s in inv.steps] == ["get_run", "submit_report"]
    # The 2nd call really received the get_run answer, under the same call id.
    asked, answered = model.histories[1][1], model.histories[1][2]
    result = answered.tool_results[0]
    assert result.call_id == asked.tool_calls[0].id and not result.is_error
    assert len(json.loads(result.content)["events"]) == 6

# Case 27

def test_case27_missing_event_goes_back_to_the_model(viewer):
    model = FakeModel(ask(name="get_event", event_id=99), submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    result = model.histories[1][2].tool_results[0]
    assert result.is_error and "no event 99" in result.content and "0–5" in result.content
    assert inv.status == "done" and inv.steps[0].ok is False

# Case 28 is replaced by case 54 (decision 0009).

# Case 29

def test_case29_step_limit(viewer):
    model = FakeModel(ask(name="get_run"))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    assert inv.status == "stopped" and inv.report is None
    assert inv.reason == f"step limit ({config.MAX_STEPS} model calls)"
    assert inv.model_calls == len(model.histories) == config.MAX_STEPS

# Case 30

def test_case30_time_limit(viewer):
    model = FakeModel(ask(name="get_run"))
    # start, turn-1 check, then past 180 s for every later read
    inv = investigator.investigate(client=viewer, model=model, run_id="ok", clock=_clock(0, 0, 200))
    assert inv.status == "stopped" and inv.reason == "time limit (180s)"
    assert inv.model_calls == 1

# Case 31

def test_case31_unknown_run_costs_nothing(viewer):
    model = FakeModel(ask(name="get_run"))
    with pytest.raises(openclaw.RunNotFound):
        investigator.investigate(client=viewer, model=model, run_id="nope")
    assert model.histories == []

# Case 32 (changed by case 51)

def test_case32_viewer_down_at_the_start_stops_before_the_model(dead_viewer):
    model = FakeModel(ask(name="get_run"))
    with pytest.raises(openclaw.ViewerUnavailable, match="dash"):
        investigator.investigate(client=dead_viewer, model=model, run_id="ok")
    assert model.histories == []            # no model call, no money spent


def test_case32_viewer_down_mid_run_no_longer_matters():
    answered = []
    def first_then_refuse(request):
        if answered:
            raise httpx.ConnectError("connection refused", request=request)
        answered.append(1)
        return fake_viewer(request=request)
    model = FakeModel(ask(name="get_run"), ask(name="get_event", event_id=3), submit(report=REPORT))
    with openclaw.make_client(transport=httpx.MockTransport(first_then_refuse)) as client:
        inv = investigator.investigate(client=client, model=model, run_id="ok")
    assert inv.status == "done"

# Case 51

def test_case51_one_investigation_fetches_the_run_once():
    requests = []
    def counting(request):
        requests.append(request.url.path)
        return fake_viewer(request=request)
    model = FakeModel(ask(name="get_run"), ask(name="get_event", event_id=1),
                      ask(name="get_event", event_id=3), ask(name="get_event", event_id=3, start=10),
                      submit(report=REPORT))
    with openclaw.make_client(transport=httpx.MockTransport(counting)) as client:
        inv = investigator.investigate(client=client, model=model, run_id="ok")
    assert inv.status == "done" and len(inv.steps) == 5
    assert requests == ["/api/run/ok"]


def test_case51_tool_answers_are_unchanged(viewer):
    # The same text the model got before: the cutting didn't change, only where the run comes from.
    model = FakeModel(ask(name="get_run"), ask(name="get_event", event_id=3), submit(report=REPORT))
    investigator.investigate(client=viewer, model=model, run_id="ok")
    answers = [r.content for m in model.histories[-1] for r in m.tool_results]
    raw = openclaw.fetch_run(client=viewer, run_id="ok")
    assert answers == [json.dumps(tools.get_run(raw=raw), ensure_ascii=False),
                       json.dumps(tools.get_event(raw=raw, event_id=3), ensure_ascii=False)]

# ---- Review fixes: cases 36–39 ----

def _clock(*times):
    """A fake clock: these times in order, then the last one forever."""
    return itertools.chain(times, itertools.repeat(times[-1])).__next__

# Case 36

def test_case36_each_call_gets_only_the_seconds_left(viewer):
    model = FakeModel(ask(name="get_run"))
    # start, turn-1 check, turn-2 check (50 s used), turn-3 check (past 180 s)
    inv = investigator.investigate(client=viewer, model=model, run_id="ok", clock=_clock(0, 0, 50, 200))
    assert model.timeouts == [180, 130]
    assert inv.status == "stopped" and inv.reason == "time limit (180s)"

def test_case36_a_call_that_ran_out_of_time_is_the_time_limit(viewer):
    model = FakeModel(ModelError("model call failed: Request timed out."))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok", clock=_clock(0, 0, 200))
    assert inv.status == "stopped" and inv.reason == "time limit (180s)"

# Case 37

def test_case37_cut_off_report_is_asked_again_shorter(viewer):
    model = FakeModel(submit(report={"outcome": "success", "summary": "The sea"}, cut_off=True),
                      submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    assert "cut off" in model.histories[1][-1].text
    assert inv.status == "done" and inv.model_calls == 2
    assert [(s.ok, s.note) for s in inv.steps] == [
        (False, "answer cut off (length limit)"), (True, "final report")]

def test_case37_tool_call_in_a_cut_off_reply_is_not_run(viewer):
    model = FakeModel(ask(name="get_event", cut_off=True, event_id=3), submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    assert [s.tool for s in inv.steps] == [None, "submit_report"]   # get_event never ran
    kept = model.histories[1][1]
    assert kept.role == "assistant" and kept.tool_calls == []   # no unanswered call
    assert inv.status == "done"

# Case 38 is retired: there is no free-text report to search (decision 0009).

# Case 39

def test_case39_model_fails_mid_run_keeps_the_steps(viewer):
    model = FakeModel(ask(name="get_run"), ask(name="get_event", event_id=3),
                      ModelError("model call failed: overloaded"))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    assert inv.status == "error" and inv.reason == "model call failed: overloaded"
    assert [s.tool for s in inv.steps] == ["get_run", "get_event"]
    assert inv.model_calls == 3 and inv.report is None

# ---- What real models do that the fake never did: cases 40–45 ----

def _answers(model, call):
    """The tool results the model received on call number `call` (1-based)."""
    return [json.loads(r.content) if not r.is_error else r
            for r in model.histories[call - 1][-1].tool_results]

# Case 40

def test_case40_text_plus_tool_call(viewer):
    model = FakeModel(ask(name="get_run", text="Let me look."), submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    kept = model.histories[1][1]
    assert kept.text == "Let me look." and [c.name for c in kept.tool_calls] == ["get_run"]
    assert inv.status == "done"

# Case 41

def test_case41_several_tool_calls_answered_in_one_message(viewer):
    reply = ask_many(("get_event", {"event_id": 3}), ("get_event", {"event_id": 5}))
    model = FakeModel(reply, submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    results = model.histories[1][2].tool_results
    assert [r.call_id for r in results] == [c.id for c in reply.tool_calls]
    assert [json.loads(r.content)["id"] for r in results] == [3, 5]
    assert inv.status == "done"

# Case 42

def test_case42_long_event_read_page_by_page(viewer):
    model = FakeModel(ask(name="get_event", event_id=3), ask(name="get_event", event_id=3, start=20000),
                      submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    page1, = _answers(model=model, call=2)
    page2, = _answers(model=model, call=3)
    assert page1["next_start"] == 20000 and len(page1["content"]) == 20000
    assert page2["next_start"] is None and len(page2["content"]) == 7108
    assert inv.status == "done"

# Case 43

def test_case43_model_cannot_choose_the_run(viewer):
    model = FakeModel(ask(name="get_run", run_id="other"), submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    run, = _answers(model=model, call=2)
    # The run served at "ok" (real run 92145325), not "other" (the fake viewer 404s it).
    assert run["run_id"].startswith("92145325") and len(run["events"]) == 6
    assert inv.status == "done"

# Case 44

def test_case44_bad_tool_calls_go_back_to_the_model(viewer):
    reply = ask_many(("delete_run", {}), ("get_event", {}), ("get_event", {"event_id": "abc"}))
    model = FakeModel(reply, submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    unknown, missing, not_int = model.histories[1][2].tool_results
    assert all(r.is_error for r in (unknown, missing, not_int))
    assert "unknown tool 'delete_run'" in unknown.content
    assert "needs event_id" in missing.content
    assert "abc" in not_int.content
    assert [s.ok for s in inv.steps] == [False, False, False, True]
    assert inv.status == "done"

# Case 45

def test_case45_whole_conversation_sent_every_time(viewer):
    first, second = ask(name="get_run"), ask(name="get_event", event_id=3)
    model = FakeModel(first, second, submit(report=REPORT))
    investigator.investigate(client=viewer, model=model, run_id="ok")
    sent = model.histories[2]
    assert [m.role for m in sent] == ["user", "assistant", "user", "assistant", "user"]
    assert sent[0].text == "Investigate run ok."
    assert sent[1].tool_calls == first.tool_calls and sent[3].tool_calls == second.tool_calls
    assert sent[2].tool_results[0].call_id == first.tool_calls[0].id
    assert sent[4].tool_results[0].call_id == second.tool_calls[0].id


# ---- The report is handed in through submit_report: cases 52–55 ----

# Case 52

def test_case52_tool_schema_comes_from_report():
    spec, = [t for t in investigator.TOOLS if t.name == "submit_report"]
    schema = spec.parameters
    assert "$ref" not in json.dumps(schema) and "$defs" not in schema    # Finding inline
    assert set(schema["properties"]) == set(Report.model_fields)
    assert schema["required"] == ["outcome", "summary", "findings", "next_step"]
    assert schema["properties"]["outcome"]["enum"] == ["success", "failure", "insufficient_evidence"]
    kind = schema["properties"]["findings"]["items"]["properties"]["kind"]
    assert kind["enum"] == ["fact", "suspicion"] and "inference" in kind["description"]
    assert "submit_report" in investigator.INSTRUCTIONS
    assert '"outcome"' not in investigator.INSTRUCTIONS                     # no hand-typed copy

# Case 53

def test_case53_submit_report_finishes(viewer):
    model = FakeModel(ask(name="get_run"), submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    assert inv.status == "done" and inv.model_calls == 2
    assert inv.report.model_dump() == REPORT
    last = inv.steps[-1]
    assert (last.tool, last.ok, last.note, last.input) == ("submit_report", True, "final report", {})

def test_case53_other_tool_in_the_same_reply_runs_first(viewer):
    reply = ask_many(("get_event", {"event_id": 3}), ("submit_report", REPORT))
    inv = investigator.investigate(client=viewer, model=FakeModel(reply), run_id="ok")
    assert inv.status == "done" and inv.model_calls == 1
    assert [s.tool for s in inv.steps] == ["get_event", "submit_report"]

# Case 54

def test_case54_invalid_report_is_a_tool_error(viewer):
    missing_field = {k: v for k, v in REPORT.items() if k != "next_step"}
    bad_event = {**REPORT, "findings": [{"what": "x", "evidence": [42], "kind": "fact"}]}
    replies = [submit(report=missing_field), submit(report=bad_event), submit(report={}),
               submit(report=REPORT)]
    model = FakeModel(*replies)
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    told = [model.histories[i][-1].tool_results[0] for i in (1, 2, 3)]
    assert [r.call_id for r in told] == [r.tool_calls[0].id for r in replies[:3]]
    assert all(r.is_error for r in told)
    assert "next_step" in told[0].content
    assert "[42]" in told[1].content and "events 0–5" in told[1].content
    assert "empty" in told[2].content
    assert inv.status == "done" and inv.model_calls == 4
    assert [s.ok for s in inv.steps] == [False, False, False, True]
    assert "next_step" in inv.steps[0].note

# Case 55

def test_case55_text_reply_is_not_a_report(viewer):
    model = FakeModel(say(text=json.dumps(REPORT)), submit(report=REPORT))
    inv = investigator.investigate(client=viewer, model=model, run_id="ok")
    assert "submit_report" in model.histories[1][-1].text
    assert inv.status == "done" and inv.model_calls == 2
    assert [(s.tool, s.ok) for s in inv.steps] == [(None, False), ("submit_report", True)]
