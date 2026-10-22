"""The evaluation: run the real investigator on frozen copies of real runs and
grade each report with 3 checks in code. Used by evals/run_eval.py and the
/eval page. See docs/decisions/0011 and TEST_PLAN cases 61-74."""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from app import config, investigator
from app.adapters import openclaw
from app.models.base import Model
from app.schema import Investigation, Report, Step


class Case(BaseModel):
    """One run with its expected answer, written by hand before any model sees it."""
    id: str
    run_id: str
    note: str                                  # what happened, in plain words
    outcome: Literal["success", "failure", "insufficient_evidence"]
    must_cite: list[int]                       # every one must be in some finding's evidence
    cause_mentions: list[str]                  # any one is enough; empty = nothing went wrong

class Checks(BaseModel):
    outcome: bool
    cited: bool
    cause: bool

class Attempt(BaseModel):
    """One graded investigation. The report and steps go to the page and to
    data/eval-reports/, never to the public results file (decision 0015)."""
    case_id: str
    model: str
    status: str
    reason: str | None
    checks: Checks
    cost: float | None
    seconds: float
    model_calls: int
    report: Report | None = None
    steps: list[Step] = []

class CasesBroken(Exception):
    """cases.json can't be read or a case is invalid."""

class SnapshotMissing(Exception):
    """The case's run has no saved copy yet."""


# ---- Dataset: the cases and the saved copies ----

def load_cases() -> list[Case]:
    # A typo must fail loudly, never become a case no model can pass (case 63).
    try:
        rows = json.loads(config.EVAL_CASES.read_text())
    except (OSError, ValueError) as ex:
        raise CasesBroken(f"can't read {config.EVAL_CASES.name}: {ex}") from ex
    cases = []
    for i, row in enumerate(rows):
        try:
            cases.append(Case.model_validate(row))
        except ValidationError as ex:
            name = row.get("id", f"#{i + 1}") if isinstance(row, dict) else f"#{i + 1}"
            raise CasesBroken(f"case {name} in {config.EVAL_CASES.name} is invalid: {ex}") from ex
    return cases

def find_case(case_id: str) -> Case | None:
    return next((c for c in load_cases() if c.id == case_id), None)

def snapshot_path(run_id: str) -> Path:
    return config.EVAL_RUNS_DIR / f"{run_id}.json"

def save_snapshot(client: httpx.Client, run_id: str) -> Path:
    """Save the viewer's answer for a run, once. Never overwrites: the copy must stay frozen."""
    path = snapshot_path(run_id=run_id)
    if path.exists():
        raise FileExistsError(f"{path} already exists; delete it first to save a new copy")
    # Fetched before anything is written, so a missing run or a closed tunnel leaves no file.
    raw = openclaw.fetch_run(client=client, run_id=run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1))
    return path

def require_snapshot(run_id: str) -> Path:
    path = snapshot_path(run_id=run_id)
    if not path.exists():
        raise SnapshotMissing(f"no saved copy of run {run_id}; save it with "
                              f"`uv run python -m evals.snapshot {run_id}` (tunnel open)")
    return path

def replay_client(run_id: str) -> httpx.Client:
    """A fake viewer that answers /api/run/<run_id> from the saved copy, and nothing else."""
    raw = json.loads(require_snapshot(run_id=run_id).read_text())

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/run/{run_id}":
            return httpx.Response(200, json=raw)
        return httpx.Response(404, json={"error": "not in the saved copy"})

    return openclaw.make_client(transport=httpx.MockTransport(answer))


# ---- Task and score ----

def grade(inv: Investigation, case: Case) -> Checks:
    # No report (stopped or error) fails every check: not finishing is a result (case 66).
    rp = inv.report
    if inv.status != "done" or rp is None:
        return Checks(outcome=False, cited=False, cause=False)
    cited = {e for f in rp.findings for e in f.evidence}
    cause = (rp.suspected_cause or "").lower()
    return Checks(outcome=rp.outcome == case.outcome,
                  cited=set(case.must_cite) <= cited,
                  # Nothing went wrong: the right answer names no cause.
                  cause=(any(w.lower() in cause for w in case.cause_mentions)
                         if case.cause_mentions else not cause))

def run_attempt(case: Case, model: Model) -> Attempt:
    """One real investigation of the case's saved copy, graded."""
    with replay_client(run_id=case.run_id) as client:
        inv = investigator.investigate(client=client, model=model, run_id=case.run_id)
    return Attempt(case_id=case.id, model=model.name, status=inv.status, reason=inv.reason,
                   checks=grade(inv=inv, case=case), cost=inv.cost, seconds=inv.seconds,
                   model_calls=inv.model_calls, report=inv.report, steps=inv.steps)


# ---- The results table ----

def _avg(values: list) -> float | None:
    # Unknown if any value is unknown: averaging only the known ones would look cheaper (case 67).
    return None if not values or None in values else sum(values) / len(values)

def results_markdown(attempts: list[Attempt], when: datetime) -> str:
    """Scores, cost, time and reasons only: report text quotes the run, and the repo is public."""
    lines = [f"# Eval results — {when:%Y-%m-%d %H:%M}", ""]
    for case_id in dict.fromkeys(a.case_id for a in attempts):
        rows = [a for a in attempts if a.case_id == case_id]
        lines += [f"## Case `{case_id}`", "",
                  "| model | outcome | cited | cause | avg cost | avg time | model calls |",
                  "|---|---|---|---|---|---|---|"]
        for model in dict.fromkeys(a.model for a in rows):
            mine = [a for a in rows if a.model == model]
            n = len(mine)
            cost = _avg(values=[a.cost for a in mine])
            score = lambda check: f"{sum(getattr(a.checks, check) for a in mine)}/{n}"
            lines.append(f"| {model} | {score('outcome')} | {score('cited')} | {score('cause')} | "
                         + ("?" if cost is None else f"${cost:.4f}")
                         + f" | {_avg(values=[a.seconds for a in mine]):.1f}s"
                         + f" | {_avg(values=[a.model_calls for a in mine]):.1f} |")
        stopped = [a for a in rows if a.status != "done"]
        if stopped:
            lines += ["", "Didn't finish:"]
            lines += [f"- {a.model}: {a.status} — {a.reason}" for a in stopped]
        lines.append("")
    return "\n".join(lines)

def reports_json(attempts: list[Attempt], when: datetime) -> str:
    """Every attempt in full, numbered per case and model (case 85). Quotes the runs: data/ only."""
    seen: dict[tuple[str, str], int] = {}
    rows = []
    for a in attempts:
        key = (a.case_id, a.model)
        seen[key] = seen.get(key, 0) + 1
        rows.append({"attempt": seen[key], **a.model_dump()})
    return json.dumps({"when": when.isoformat(timespec="seconds"), "attempts": rows},
                      ensure_ascii=False, indent=1)

def write_results(attempts: list[Attempt], when: datetime | None = None) -> Path:
    """The public scores file, and the reports behind it under the same name (decision 0015)."""
    when = when or datetime.now()
    name = f"{when:%Y-%m-%d-%H%M%S}"
    config.EVAL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.EVAL_REPORTS_DIR / f"{name}.json").write_text(reports_json(attempts=attempts, when=when))
    config.EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.EVAL_RESULTS_DIR / f"{name}.md"
    path.write_text(results_markdown(attempts=attempts, when=when))
    return path

# Only names write_results makes, so a request can't reach any other file (case 77).
RESULTS_NAME = re.compile(r"\d{4}-\d{2}-\d{2}-\d{6}\.md")

def list_results() -> list[str]:
    """The saved results files, newest first (case 76)."""
    if not config.EVAL_RESULTS_DIR.is_dir():
        return []
    return sorted((p.name for p in config.EVAL_RESULTS_DIR.iterdir()
                   if RESULTS_NAME.fullmatch(p.name)), reverse=True)

def read_results(name: str) -> str | None:
    if not RESULTS_NAME.fullmatch(name):
        return None
    path = config.EVAL_RESULTS_DIR / name
    return path.read_text() if path.is_file() else None
