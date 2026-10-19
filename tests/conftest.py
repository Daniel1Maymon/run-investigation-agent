"""A fake trace viewer and a fake model, so the tests run without the server,
the tunnel or an API key."""
import itertools
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.adapters import openclaw
from app.main import app, viewer_client
from app.models.base import ModelReply, ToolCall

# A real run (92145325, success, 6 events), saved redacted: real structure, no content.
OK_RUN = json.loads((Path(__file__).parent / "fixtures" / "run_92145325.json").read_text())

RUN = {"run_id": "r1", "agent": "nunu", "status": "success",
       "detail": {"messages": [], "calls": [], "tools": [], "meta": {}}}


SESSIONS = {"rows": [
    {"session_id": "s1", "agent": "nunu", "started_ts": "2026-10-17T06:00:00Z",
     "failed": 0, "user_text": "hello",
     "runs": [{"run_id": "r1", "status": "success", "started_ts": "2026-10-17T06:00:00Z"}]},
    {"session_id": "s2", "agent": "assistant", "started_ts": "2026-10-16T05:00:00Z",
     "failed": 1, "user_text": None,
     "runs": [{"run_id": "r2", "status": "success", "started_ts": "2026-10-16T05:00:00Z"},
              {"run_id": "r3", "status": "error", "started_ts": "2026-10-16T05:10:00Z"}]},
]}

def fake_viewer(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/version":
        return httpx.Response(200, json={"v": 0})
    if path == "/api/runs":
        return httpx.Response(200, json=SESSIONS)
    if path == "/api/run/r1":
        return httpx.Response(200, json=RUN)
    if path == "/api/run/ok":
        return httpx.Response(200, json=OK_RUN)
    if path == "/api/run/boom":
        return httpx.Response(500, json={"error": "kaboom"})
    if path.startswith("/api/run/"):
        return httpx.Response(404, json={"error": "no such run"})
    return httpx.Response(404, text="not found")


def refused(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


@pytest.fixture
def viewer():
    with openclaw.make_client(httpx.MockTransport(fake_viewer)) as c:
        yield c


@pytest.fixture
def dead_viewer():
    with openclaw.make_client(httpx.MockTransport(refused)) as c:
        yield c


def _api(client):
    app.dependency_overrides[viewer_client] = lambda: client
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def api(viewer):
    yield from _api(viewer)


@pytest.fixture
def api_viewer_down(dead_viewer):
    yield from _api(dead_viewer)


# ---- The fake model ----

class FakeModel:
    """Replies from a script, in order; the last reply repeats forever. A reply
    that is an exception is raised instead. Records every history and timeout it
    was sent, so tests can check what the loop told the model."""
    name = "fake-model"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.histories = []
        self.timeouts = []

    def next(self, instructions, tools, history, *, timeout):
        self.histories.append([m.model_copy(deep=True) for m in history])
        self.timeouts.append(timeout)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


_ids = itertools.count(1)

def ask(name, text="", cut_off=False, **tool_input):
    """A model reply asking for one tool, optionally with some text."""
    return ModelReply(text=text, tool_calls=[ToolCall(id=f"call_{next(_ids)}", name=name,
                                                       input=tool_input)], cut_off=cut_off)

def ask_many(*calls):
    """A model reply asking for several tools at once: (name, input) pairs."""
    return ModelReply(text="", tool_calls=[ToolCall(id=f"call_{next(_ids)}", name=n, input=i)
                                           for n, i in calls])

def say(text, cut_off=False):
    """A model reply with no tool calls: plain text, which is not a report (decision 0009)."""
    return ModelReply(text=text, tool_calls=[], cut_off=cut_off)

def submit(report, cut_off=False):
    """A model reply handing in a report through submit_report: how the model finishes."""
    return ModelReply(text="", tool_calls=[ToolCall(id=f"call_{next(_ids)}", name="submit_report",
                                                    input=report)], cut_off=cut_off)

REPORT = {"outcome": "success", "summary": "The search returned results and the reply answered.",
          "findings": [{"what": "family_search returned results", "evidence": [3], "kind": "fact"},
                       {"what": "the reply answered the question", "evidence": [5], "kind": "fact"}],
          "suspected_cause": None, "next_step": "Nothing to fix."}
