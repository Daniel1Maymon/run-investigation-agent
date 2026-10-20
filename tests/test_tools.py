"""TEST_PLAN.md cases 17–22: the investigator's tools and the translation behind them.

Fixtures are real runs saved with scripts/save_run.py --redact: real structure
and lengths, every free text replaced by dots."""
import json
from pathlib import Path

import pytest

from app import tools
from app.adapters import openclaw

FIXTURES = Path(__file__).parent / "fixtures"
OK_RUN = json.loads((FIXTURES / "run_92145325.json").read_text())
FAILED_RUN = json.loads((FIXTURES / "run_51bb2e1a.json").read_text())

def kinds(overview):
    return [e.kind for e in overview.events]

# Case 17

def test_case17_success_run_becomes_events():
    o = openclaw.to_overview(raw=OK_RUN)
    assert kinds(overview=o) == ["user", "thinking", "tool_call", "tool_result", "thinking", "reply"]
    assert o.events[2].tool == o.events[3].tool == "family_search"
    assert o.events[3].chars == 27_108
    assert o.recorded_status == "success" and o.source == "openclaw"
    assert o.missing == [] and o.failure_kind is None and o.error_text is None

# Case 18

def test_case18_failed_run_becomes_events():
    o = openclaw.to_overview(raw=FAILED_RUN)
    assert kinds(overview=o) == ["user", "thinking", "tool_call", "tool_call",
                        "tool_result", "tool_result", "reply"]
    assert {e.tool for e in o.events if e.kind == "tool_call"} == {"google_assi"}
    assert o.events[-1].chars == 0
    assert "idleTimedOut" in o.flags
    assert o.recorded_status == "error" and o.failure_kind == "idle timeout"
    assert "idle timeout" in o.error_text

# Case 19

@pytest.mark.parametrize("raw", [OK_RUN, FAILED_RUN], ids=["ok", "failed"])
def test_case19_previews_are_short_and_say_so(raw):
    for e in openclaw.to_overview(raw=raw).events:
        assert len(e.preview) <= openclaw.PREVIEW_CHARS
        assert e.shortened == (e.chars > openclaw.PREVIEW_CHARS)

# Case 20

def test_case20_long_event_comes_in_pages():
    p1 = openclaw.event_detail(raw=OK_RUN, event_id=3)
    assert (p1.chars, len(p1.content), p1.next_start) == (27_108, 20_000, 20_000)
    p2 = openclaw.event_detail(raw=OK_RUN, event_id=3, start=p1.next_start)
    assert (len(p2.content), p2.next_start) == (7_108, None)
    assert p1.source_ref == "message 2, block 0" and p1.tool == "family_search"

def test_case20_unknown_event_names_the_valid_range():
    with pytest.raises(openclaw.EventNotFound, match="0–5"):
        openclaw.event_detail(raw=OK_RUN, event_id=6)
    with pytest.raises(openclaw.EventNotFound):
        openclaw.event_detail(raw=OK_RUN, event_id=-1)

# Case 21

def test_case21_deleted_log_file_is_said_out_loud():
    raw = {"run_id": "gone", "agent": "nunu", "status": "success",
           "detail": {"error": "trajectory file missing: /x/y.jsonl"}}
    o = openclaw.to_overview(raw=raw)
    assert o.events == []
    assert o.missing == ["run detail unavailable: trajectory file missing: /x/y.jsonl"]
    assert o.agent == "nunu" and o.recorded_status == "success"
    with pytest.raises(openclaw.EventNotFound, match="none"):
        openclaw.event_detail(raw=raw, event_id=0)

# Case 22

def test_case22_prior_context_and_dropped_content_are_marked():
    raw = {"run_id": "r", "detail": {"messages": [
        {"i": 0, "role": "user", "prior": True, "offset": -5000,
         "blocks": [{"kind": "text", "text": "an earlier question"}]},
        {"i": 1, "role": "toolResult", "toolName": "read", "isError": True, "prior": False,
         "blocks": [{"kind": "text", "text": "[not recorded: 40,000 chars, over OpenClaw's 32,768-char trace limit]"}]},
    ]}}
    e0, e1 = openclaw.to_overview(raw=raw).events
    assert e0.prior and e0.offset_ms == -5000 and not e0.not_recorded
    assert not e1.prior and e1.not_recorded and e1.is_error and e1.tool == "read"

# The tools themselves: cut down a fetched run, return plain JSON.

def test_tools_return_plain_json(viewer):
    o = tools.get_run(raw=openclaw.fetch_run(client=viewer, run_id="r1"))
    assert o["run_id"] == "r1" and o["events"] == []
    json.dumps(o)  # what the model will receive must serialise
