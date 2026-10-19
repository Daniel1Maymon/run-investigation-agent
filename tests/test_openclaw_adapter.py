"""TEST_PLAN.md cases 3–5, 12, 14 and 57."""
import json
from pathlib import Path

import httpx
import pytest

from app.adapters import openclaw
from tests.conftest import RUN

FIXTURES = Path(__file__).parent / "fixtures"


def test_case3_existing_run_returned_unchanged(viewer):
    assert openclaw.fetch_run(client=viewer, run_id="r1") == RUN


def test_case4_missing_run_raises_run_not_found(viewer):
    with pytest.raises(expected_exception=openclaw.RunNotFound, match="nope"):
        openclaw.fetch_run(client=viewer, run_id="nope")


def test_case5_unreachable_viewer_points_at_the_tunnel(dead_viewer):
    with pytest.raises(expected_exception=openclaw.ViewerUnavailable, match="dash"):
        openclaw.fetch_run(client=dead_viewer, run_id="r1")


def test_case5_viewer_error_is_unavailable(viewer):
    with pytest.raises(expected_exception=openclaw.ViewerUnavailable, match="500"):
        openclaw.fetch_run(client=viewer, run_id="boom")

# Cases 12 and 14 — the session list.

def test_case12_ok_session_is_slimmed(viewer):
    assert openclaw.list_sessions(client=viewer)[0] == {
        "session_id": "s1", "agent": "nunu", "started_ts": "2026-10-17T06:00:00Z",
        "status": "ok", "failed_runs": 0, "first_prompt": "hello",
        "runs": [{"run_id": "r1", "status": "success", "started_ts": "2026-10-17T06:00:00Z"}]}

def test_case12_one_failed_run_fails_the_session(viewer):
    s = openclaw.list_sessions(client=viewer)[1]
    assert s["status"] == "failed" and s["failed_runs"] == 1
    assert [r["run_id"] for r in s["runs"]] == ["r2", "r3"]
    assert s["first_prompt"] == ""

def test_case12_unreachable_viewer_points_at_the_tunnel(dead_viewer):
    with pytest.raises(expected_exception=openclaw.ViewerUnavailable, match="dash"):
        openclaw.list_sessions(client=dead_viewer)

def test_case14_real_viewer_answer_slims_without_errors():
    rows = json.loads(s=(FIXTURES / "api_runs_sample.json").read_text())["rows"]
    slim = [openclaw._slim_session(row=r) for r in rows]
    assert slim
    assert all(s["status"] in ("ok", "failed") and s["runs"] for s in slim)

# Case 57 — the viewer's data version.

def test_case57_data_version_is_returned(viewer):
    assert openclaw.data_version(client=viewer) == 0

def test_case57_unreachable_viewer_points_at_the_tunnel(dead_viewer):
    with pytest.raises(expected_exception=openclaw.ViewerUnavailable, match="dash"):
        openclaw.data_version(client=dead_viewer)

def test_case57_viewer_error_is_unavailable():
    erroring = httpx.MockTransport(handler=lambda request: httpx.Response(status_code=500))
    with openclaw.make_client(transport=erroring) as client:
        with pytest.raises(expected_exception=openclaw.ViewerUnavailable, match="500"):
            openclaw.data_version(client=client)
