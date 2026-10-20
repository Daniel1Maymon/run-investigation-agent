"""TEST_PLAN.md cases 6, 23 and 33."""
from tests.conftest import RUN


def test_case6_run_passes_through(api):
    r = api.get("/runs/r1")
    assert r.status_code == 200
    assert r.json() == RUN


def test_case6_unknown_run_is_404(api):
    assert api.get("/runs/nope").status_code == 404


def test_case6_viewer_down_is_503(api_viewer_down):
    r = api_viewer_down.get("/runs/r1")
    assert r.status_code == 503
    assert "dash" in r.json()["detail"]


def test_case23_overview_url(api):
    r = api.get("/runs/r1/overview")
    assert r.status_code == 200
    assert r.json()["run_id"] == "r1" and r.json()["source"] == "openclaw"


def test_case23_unknown_run_overview_is_404(api):
    assert api.get("/runs/nope/overview").status_code == 404


def test_case23_unknown_event_is_404(api):
    r = api.get("/runs/r1/events/99")
    assert r.status_code == 404
    assert "no event 99" in r.json()["detail"]


def test_case23_viewer_down_is_503_on_both_urls(api_viewer_down):
    for url in ("/runs/r1/overview", "/runs/r1/events/0"):
        r = api_viewer_down.get(url)
        assert r.status_code == 503 and "dash" in r.json()["detail"]


# Case 33: POST /runs/{id}/investigate

import json  # noqa: E402

from app.main import app, model_client  # noqa: E402
from app.models.base import ModelError  # noqa: E402
from tests.conftest import REPORT, FakeModel, ask, say, submit  # noqa: E402


def _with_model(model):
    app.dependency_overrides[model_client] = lambda: model


def test_case33_investigate_returns_the_investigation(api):
    _with_model(model=FakeModel(ask(name="get_run"), submit(report=REPORT)))
    r = api.post("/runs/ok/investigate")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done" and body["report"]["outcome"] == "success"
    assert body["model"] == "fake-model" and body["model_calls"] == 2


def test_case33_unknown_run_is_404(api):
    _with_model(model=FakeModel(ask(name="get_run")))
    assert api.post("/runs/nope/investigate").status_code == 404


def test_case33_viewer_down_is_503(api_viewer_down):
    _with_model(model=FakeModel(ask(name="get_run")))
    r = api_viewer_down.post("/runs/ok/investigate")
    assert r.status_code == 503 and "dash" in r.json()["detail"]


def test_case33_no_key_is_503(api, monkeypatch):
    monkeypatch.setattr("app.config.MODEL_PROVIDER", "openrouter")   # the default
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = api.post("/runs/ok/investigate")     # the real model_client, no key
    assert r.status_code == 503 and "OPENROUTER_API_KEY" in r.json()["detail"]


def test_case33_model_failure_is_an_error_status_not_502(api):
    # Case 39: the steps done so far come back with it.
    _with_model(model=FakeModel(ask(name="get_run"), ModelError("model call failed: overloaded")))
    r = api.post("/runs/ok/investigate")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error" and "model call failed" in body["reason"]
    assert [s["tool"] for s in body["steps"]] == ["get_run"] and body["report"] is None


def test_case33_get_is_not_allowed(api):
    assert api.get("/runs/ok/investigate").status_code == 405
