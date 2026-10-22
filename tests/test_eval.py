"""TEST_PLAN.md cases 61-67, 70-73, 76-77 and 85-87: the eval, with fake models and saved
copies in a temporary folder. Cases 68, 74, 78 and 88 use real models and are verified live."""
import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, evaluation
from app.adapters import openclaw
from app.main import app, model_maker
from app.models.base import ModelError
from app.schema import Investigation, Report, Step
from evals import run_eval
from tests.conftest import REPORT, FakeModel, OK_RUN, ask, fake_viewer, refused, submit

RUN_ID = OK_RUN["run_id"]
CASE = {"id": "c1", "run_id": RUN_ID, "note": "a test case", "outcome": "failure",
        "must_cite": [5], "cause_mentions": ["email", "מייל"]}
RIGHT = {**REPORT, "outcome": "failure", "suspected_cause": "No Email tool is connected.",
         "findings": [{"what": "the reply says it can't", "evidence": [1, 5], "kind": "fact"}]}


@pytest.fixture
def eval_dirs(tmp_path, monkeypatch):
    """cases.json with one case, and empty copy and results folders, all temporary."""
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([CASE]))
    monkeypatch.setattr(config, "EVAL_CASES", cases)
    monkeypatch.setattr(config, "EVAL_RUNS_DIR", tmp_path / "eval-runs")
    monkeypatch.setattr(config, "EVAL_RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(config, "EVAL_REPORTS_DIR", tmp_path / "data" / "eval-reports")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return tmp_path

@pytest.fixture
def saved(eval_dirs):
    """The case's run, already saved."""
    with openclaw.make_client(transport=httpx.MockTransport(fake_viewer)) as c:
        _save_ok(client=c)
    return eval_dirs

def _save_ok(client):
    # fake_viewer serves OK_RUN as "ok"; save it under its real id.
    path = evaluation.snapshot_path(run_id=RUN_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(openclaw.fetch_run(client=client, run_id="ok")))

def _inv(status="done", report=RIGHT):
    return Investigation(run_id=RUN_ID, model="m", status=status, model_calls=1, seconds=1.0, steps=[],
                         report=Report.model_validate(report) if report else None,
                         reason=None if status == "done" else "step limit (12 model calls)")

def _case():
    return evaluation.Case.model_validate(CASE)

# Case 61

def test_case61_snapshot_saves_the_viewer_answer(eval_dirs, viewer):
    path = evaluation.save_snapshot(client=viewer, run_id="ok")
    assert json.loads(path.read_text()) == openclaw.fetch_run(client=viewer, run_id="ok")
    assert path == config.EVAL_RUNS_DIR / "ok.json"

def test_case61_snapshot_never_overwrites(eval_dirs, viewer):
    path = evaluation.save_snapshot(client=viewer, run_id="ok")
    path.write_text('"frozen"')
    with pytest.raises(FileExistsError):
        evaluation.save_snapshot(client=viewer, run_id="ok")
    assert path.read_text() == '"frozen"'

def test_case61_snapshot_writes_nothing_on_failure(eval_dirs, viewer, dead_viewer):
    with pytest.raises(openclaw.RunNotFound):
        evaluation.save_snapshot(client=viewer, run_id="nope")
    with pytest.raises(openclaw.ViewerUnavailable, match="dash"):
        evaluation.save_snapshot(client=dead_viewer, run_id="ok")
    assert not config.EVAL_RUNS_DIR.exists() or not any(config.EVAL_RUNS_DIR.iterdir())

# Case 62

def test_case62_replay_serves_the_saved_copy(saved, viewer):
    from app import tools
    with evaluation.replay_client(run_id=RUN_ID) as c:
        raw = openclaw.fetch_run(client=c, run_id=RUN_ID)
    live = openclaw.fetch_run(client=viewer, run_id="ok")
    assert tools.get_run(raw=raw) == tools.get_run(raw=live)
    assert tools.get_event(raw=raw, event_id=3) == tools.get_event(raw=live, event_id=3)

def test_case62_attempt_reads_only_the_copy(saved):
    model = FakeModel(ask(name="get_run"), ask(name="get_event", event_id=5), submit(report=RIGHT))
    attempt = evaluation.run_attempt(case=_case(), model=model)
    assert attempt.status == "done" and attempt.checks.model_dump() == {"outcome": True, "cited": True, "cause": True}

def test_case62_missing_copy_costs_nothing(eval_dirs):
    model = FakeModel(ask(name="get_run"))
    with pytest.raises(evaluation.SnapshotMissing, match="evals.snapshot"):
        evaluation.run_attempt(case=_case(), model=model)
    assert model.histories == []

# Case 63

def test_case63_cases_load(eval_dirs):
    assert evaluation.load_cases() == [_case()]

@pytest.mark.parametrize("change", [{"outcome": "fail"}, {"must_cite": None}])
def test_case63_broken_case_names_itself(eval_dirs, change):
    bad = {**CASE, **change}
    if change.get("must_cite", 0) is None:
        del bad["must_cite"]
    config.EVAL_CASES.write_text(json.dumps([bad]))
    with pytest.raises(evaluation.CasesBroken, match="case c1"):
        evaluation.load_cases()

def test_case63_unreadable_file(eval_dirs):
    config.EVAL_CASES.write_text("[{not json")
    with pytest.raises(evaluation.CasesBroken):
        evaluation.load_cases()

# Case 64

def test_case64_correct_report_passes_all(eval_dirs):
    checks = evaluation.grade(inv=_inv(), case=_case())
    assert checks.model_dump() == {"outcome": True, "cited": True, "cause": True}

def test_case64_hebrew_cause_counts(eval_dirs):
    checks = evaluation.grade(inv=_inv(report={**RIGHT, "suspected_cause": "אין חיבור למייל"}), case=_case())
    assert checks.cause

# Case 65

@pytest.mark.parametrize("change, failed", [
    ({"outcome": "success"}, "outcome"),
    ({"findings": [{"what": "x", "evidence": [1, 3], "kind": "fact"}]}, "cited"),
    ({"suspected_cause": "The model timed out."}, "cause"),
    ({"suspected_cause": None}, "cause"),
])
def test_case65_each_check_fails_alone(eval_dirs, change, failed):
    checks = evaluation.grade(inv=_inv(report={**RIGHT, **change}), case=_case()).model_dump()
    assert [k for k, ok in checks.items() if not ok] == [failed]

def test_case65_evidence_in_any_finding(eval_dirs):
    report = {**RIGHT, "findings": [{"what": "a", "evidence": [1], "kind": "fact"},
                                    {"what": "b", "evidence": [5, 4], "kind": "suspicion"}]}
    assert evaluation.grade(inv=_inv(report=report), case=_case()).cited

def test_case65_no_problem_case_wants_no_cause(eval_dirs):
    ok_case = _case().model_copy(update={"outcome": "success", "must_cite": [], "cause_mentions": []})
    good = {**RIGHT, "outcome": "success", "suspected_cause": None}
    assert evaluation.grade(inv=_inv(report=good), case=ok_case).cause
    assert not evaluation.grade(inv=_inv(report={**good, "suspected_cause": "something"}), case=ok_case).cause

# Case 66

@pytest.mark.parametrize("status", ["stopped", "error"])
def test_case66_unfinished_fails_every_check(eval_dirs, status):
    checks = evaluation.grade(inv=_inv(status=status, report=None), case=_case())
    assert checks.model_dump() == {"outcome": False, "cited": False, "cause": False}

# Case 67

def _priced(reply, cost):
    return reply.model_copy(update={"cost": cost})

def test_case67_run_eval_with_fake_models(saved, monkeypatch):
    # The real viewer must never be called: make every new client refuse.
    real = openclaw.make_client
    monkeypatch.setattr(openclaw, "make_client",
                        lambda transport=None: real(transport=transport or httpx.MockTransport(refused)))
    def make(name):
        if name == "good":
            m = FakeModel(_priced(ask(name="get_run"), 0.001), _priced(submit(report=RIGHT), 0.002))
        else:
            m = FakeModel(ModelError("overloaded"))
        m.name = name
        return m
    attempts = run_eval.main(attempts=3, model_names=["good", "broken"], make_model=make)
    assert len(attempts) == 6
    md = evaluation.results_markdown(attempts=attempts, when=datetime(2026, 10, 20, 12, 0))
    assert "| good | 3/3 | 3/3 | 3/3 | $0.0030 |" in md
    assert "| broken | 0/3 | 0/3 | 0/3 | $0.0000 |" in md
    assert md.count("broken: error — ") == 3
    # Scores only: no report text reaches the file.
    assert RIGHT["summary"] not in md and RIGHT["findings"][0]["what"] not in md

def test_case67_unknown_cost_is_not_averaged(eval_dirs):
    base = dict(case_id="c1", model="m", status="done", reason=None, seconds=1.0, model_calls=1,
                checks=evaluation.Checks(outcome=True, cited=True, cause=True))
    md = evaluation.results_markdown(attempts=[evaluation.Attempt(**base, cost=0.01),
                                               evaluation.Attempt(**base, cost=None)],
                                     when=datetime(2026, 10, 20))
    assert "| m | 2/2 | 2/2 | 2/2 | ? |" in md

# ---- The page's API (cases 70-73) ----

@pytest.fixture
def eval_api():
    made = []
    def make(name):
        m = FakeModel(ask(name="get_run"), submit(report=RIGHT))
        m.name = name
        made.append(m)
        return m
    app.dependency_overrides[model_maker] = lambda: make
    try:
        yield TestClient(app), made
    finally:
        app.dependency_overrides.clear()

MODEL = config.EVAL_MODELS[0]

# Case 71

def test_case71_cases_endpoint(saved, eval_api):
    api, _ = eval_api
    body = api.get("/eval/cases").json()
    assert body["cases"] == [{**CASE, "snapshot": True}]
    assert body["models"] == config.EVAL_MODELS and body["attempts"] == config.EVAL_ATTEMPTS

def test_case71_broken_cases_is_an_error(eval_dirs, eval_api):
    api, _ = eval_api
    config.EVAL_CASES.write_text("[{not json")
    r = api.get("/eval/cases")
    assert r.status_code == 500 and "cases.json" in r.json()["detail"]

# Case 72

def test_case72_one_attempt(saved, eval_api):
    api, made = eval_api
    r = api.post("/eval/cases/c1/attempts", json={"model": MODEL})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == MODEL and body["status"] == "done"
    assert body["checks"] == {"outcome": True, "cited": True, "cause": True}
    assert body["report"]["outcome"] == "failure" and len(made) == 1

def test_case72_refusals(saved, eval_api):
    api, made = eval_api
    assert api.post("/eval/cases/nope/attempts", json={"model": MODEL}).status_code == 404
    assert api.post("/eval/cases/c1/attempts", json={"model": "some/other-model"}).status_code == 400
    assert made == []

def test_case72_missing_copy(eval_dirs, eval_api):
    api, made = eval_api
    r = api.post("/eval/cases/c1/attempts", json={"model": MODEL})
    assert r.status_code == 409 and "evals.snapshot" in r.json()["detail"]
    assert made == []                       # no model made, no money spent

# Case 73

def test_case73_save_results(saved, eval_api):
    api, _ = eval_api
    attempt = api.post("/eval/cases/c1/attempts", json={"model": MODEL}).json()
    r = api.post("/eval/results", json={"attempts": [attempt]})
    assert r.status_code == 200 and r.json()["path"].startswith("results/")
    md = (config.ROOT / r.json()["path"]).read_text()
    assert f"| {MODEL} | 1/1 | 1/1 | 1/1 |" in md and RIGHT["summary"] not in md

def test_case73_nothing_to_save(eval_dirs, eval_api):
    api, _ = eval_api
    assert api.post("/eval/results", json={"attempts": []}).status_code == 400
    assert not config.EVAL_RESULTS_DIR.exists()

# Case 76

def test_case76_no_results_yet(eval_dirs, eval_api):
    api, _ = eval_api
    assert api.get("/eval/results").json() == []

def test_case76_lists_results_newest_first(eval_dirs, eval_api):
    api, _ = eval_api
    for when in (datetime(2026, 10, 19, 9, 0, 0), datetime(2026, 10, 20, 14, 47, 35)):
        evaluation.write_results(attempts=[], when=when)
    (config.EVAL_RESULTS_DIR / "notes.txt").write_text("not a result")
    assert api.get("/eval/results").json() == [{"name": "2026-10-20-144735.md"},
                                               {"name": "2026-10-19-090000.md"}]

# Case 77

def test_case77_read_one_result(eval_dirs, eval_api):
    api, _ = eval_api
    evaluation.write_results(attempts=[], when=datetime(2026, 10, 20, 14, 47, 35))
    r = api.get("/eval/results/2026-10-20-144735.md")
    assert r.status_code == 200 and r.json()["text"].startswith("# Eval results — 2026-10-20 14:47")

def test_case77_refuses_other_names(eval_dirs, eval_api):
    api, _ = eval_api
    assert api.get("/eval/results/2026-01-01-000000.md").status_code == 404
    assert api.get("/eval/results/cases.json").status_code == 404
    assert api.get("/eval/results/..%2Fcases.json").status_code == 404
    assert evaluation.read_results(name="../cases.json") is None

# ---- The reports behind the scores (cases 85-87, decision 0015) ----

def _attempt(model, status="done", report=RIGHT):
    return evaluation.Attempt(
        case_id="c1", model=model, status=status, cost=0.001, seconds=1.0, model_calls=2,
        reason=None if status == "done" else "model call failed: overloaded",
        checks=evaluation.Checks(outcome=True, cited=True, cause=True),
        report=Report.model_validate(report) if report else None,
        steps=[Step(tool="get_run", result_chars=100)])

# Case 85

def test_case85_write_results_saves_the_reports(eval_dirs):
    attempts = [_attempt(model="a"), _attempt(model="b"), _attempt(model="a"),
                _attempt(model="b", status="error", report=None)]
    md = evaluation.write_results(attempts=attempts, when=datetime(2026, 10, 21, 15, 59, 39))
    saved = config.EVAL_REPORTS_DIR / "2026-10-21-155939.json"
    assert md.name == "2026-10-21-155939.md" and saved.is_file()
    rows = json.loads(saved.read_text())["attempts"]
    assert [(r["model"], r["attempt"]) for r in rows] == [("a", 1), ("b", 1), ("a", 2), ("b", 2)]
    assert rows[0]["case_id"] == "c1" and rows[0]["checks"]["cause"] is True
    assert rows[0]["report"]["summary"] == RIGHT["summary"]
    assert rows[0]["steps"][0]["tool"] == "get_run"
    assert rows[3]["report"] is None and rows[3]["reason"] == "model call failed: overloaded"
    # The public file still holds scores only.
    assert RIGHT["summary"] not in md.read_text()

# Case 86

def test_case86_attempt_carries_its_steps(saved):
    model = FakeModel(ask(name="get_run"), ask(name="get_event", event_id=5), submit(report=RIGHT))
    attempt = evaluation.run_attempt(case=_case(), model=model)
    assert [s.tool for s in attempt.steps] == ["get_run", "get_event", "submit_report"]
    assert attempt.steps[1].input == {"event_id": 5}

def test_case86_page_round_trip_saves_steps(saved, eval_api):
    api, _ = eval_api
    attempt = api.post("/eval/cases/c1/attempts", json={"model": MODEL}).json()
    assert [s["tool"] for s in attempt["steps"]] == ["get_run", "submit_report"]
    path = api.post("/eval/results", json={"attempts": [attempt]}).json()["path"]
    saved_file = config.EVAL_REPORTS_DIR / Path(path).with_suffix(".json").name
    row = json.loads(saved_file.read_text())["attempts"][0]
    assert row["report"]["outcome"] == "failure"
    assert [s["tool"] for s in row["steps"]] == ["get_run", "submit_report"]

# Case 87

def test_case87_reports_folder_is_under_ignored_data():
    assert config.EVAL_REPORTS_DIR == config.ROOT / "data" / "eval-reports"
    assert "data/" in (config.ROOT / ".gitignore").read_text().splitlines()
