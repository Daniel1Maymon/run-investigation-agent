"""The API: health, the session list, one run, the investigator's two tools
(so what the investigator sees can be opened in a browser), the investigation,
and the eval (docs/decisions/0011)."""
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app import config, evaluation, investigator, logs, models, tools
from app.adapters import openclaw
from app.models.base import Model, ModelNotConfigured

logs.setup()
app = FastAPI(title="Run Investigation Agent")

UI_PAGE = Path(__file__).parent / "ui" / "index.html"
EVAL_PAGE = Path(__file__).parent / "ui" / "eval.html"


def viewer_client() -> Iterator[httpx.Client]:
    # A dependency, so tests can override it with a fake viewer.
    with openclaw.make_client() as client:
        yield client


def model_client() -> Model:
    # A dependency too, so tests can swap in a fake model.
    return models.make_model()

def model_maker() -> Callable[[str], Model]:
    # The eval picks the model per request, so it gets a maker, not one model.
    return lambda name: models.make_model(name=name)


# One place that turns the adapter's errors into HTTP answers,
# instead of the same try/except in every endpoint.
@app.exception_handler(openclaw.RunNotFound)
@app.exception_handler(openclaw.EventNotFound)
def _not_found(request: Request, ex: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(ex)}, status_code=404)


@app.exception_handler(evaluation.SnapshotMissing)
def _no_snapshot(request: Request, ex: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(ex)}, status_code=409)

@app.exception_handler(evaluation.CasesBroken)
def _cases_broken(request: Request, ex: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(ex)}, status_code=500)

@app.exception_handler(openclaw.ViewerUnavailable)
@app.exception_handler(ModelNotConfigured)
def _unavailable(request: Request, ex: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(ex)}, status_code=503)


# A failed model call is not an HTTP error: the investigator returns it as
# status "error" with the steps done so far (TEST_PLAN case 39).


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    # The whole UI is one page; it calls /runs/{run_id} itself. See docs/decisions/0002.
    return FileResponse(UI_PAGE, media_type="text/html")


@app.get("/health")
def health(client: httpx.Client = Depends(viewer_client)) -> dict:
    viewer = openclaw.viewer_status(client=client)
    return {"status": "ok" if viewer["reachable"] else "degraded", "viewer": viewer}


@app.get("/runs/{run_id}")
def get_run(run_id: str, client: httpx.Client = Depends(viewer_client)) -> dict:
    return openclaw.fetch_run(client=client, run_id=run_id)


@app.get("/runs/{run_id}/overview")
def run_overview(run_id: str, client: httpx.Client = Depends(viewer_client)) -> dict:
    # Exactly what the investigator's get_run tool returns.
    return tools.get_run(raw=openclaw.fetch_run(client=client, run_id=run_id))


@app.get("/runs/{run_id}/events/{event_id}")
def run_event(run_id: str, event_id: int, start: int = 0,
              client: httpx.Client = Depends(viewer_client)) -> dict:
    # Exactly what the investigator's get_event tool returns.
    return tools.get_event(raw=openclaw.fetch_run(client=client, run_id=run_id),
                           event_id=event_id, start=start)


@app.post("/runs/{run_id}/investigate")
def investigate_run(run_id: str, client: httpx.Client = Depends(viewer_client), model: Model = Depends(model_client)) -> dict:
    # POST, not GET: it does work (model calls cost money and take time).
    return investigator.investigate(client=client, model=model, run_id=run_id).model_dump()


@app.get("/sessions")
def list_sessions(client: httpx.Client = Depends(viewer_client)) -> list[dict]:
    # An empty list is a valid answer, so there is no 404 here.
    return openclaw.list_sessions(client=client)


@app.get("/sessions/version")
def sessions_version(client: httpx.Client = Depends(viewer_client)) -> dict:
    # The page asks this every few seconds and re-fetches /sessions only when it changes.
    return {"v": openclaw.data_version(client=client)}

# ---- The eval (TEST_PLAN cases 70-77, docs/decisions/0011) ----
# The page asks for one attempt per request and keeps the tally itself,
# so the server keeps no state between requests.

@app.get("/eval", include_in_schema=False)
def eval_page() -> FileResponse:
    return FileResponse(EVAL_PAGE, media_type="text/html")

@app.get("/eval/cases")
def eval_cases() -> dict:
    cases = [{**c.model_dump(), "snapshot": evaluation.snapshot_path(run_id=c.run_id).exists()}
             for c in evaluation.load_cases()]
    return {"cases": cases, "models": config.EVAL_MODELS, "attempts": config.EVAL_ATTEMPTS}

class AttemptRequest(BaseModel):
    model: str

@app.post("/eval/cases/{case_id}/attempts")
def eval_attempt(case_id: str, body: AttemptRequest,
                 make_model: Callable[[str], Model] = Depends(model_maker)) -> dict:
    case = evaluation.find_case(case_id=case_id)
    if case is None:
        raise HTTPException(404, f"no case {case_id!r} in cases.json")
    if body.model not in config.EVAL_MODELS:
        raise HTTPException(400, f"{body.model!r} is not one of the eval's models: {config.EVAL_MODELS}")
    # Checked before the model is made, so a missing copy costs nothing.
    evaluation.require_snapshot(run_id=case.run_id)
    return evaluation.run_attempt(case=case, model=make_model(body.model)).model_dump()

class ResultsRequest(BaseModel):
    attempts: list[evaluation.Attempt]

@app.post("/eval/results")
def eval_results(body: ResultsRequest) -> dict:
    if not body.attempts:
        raise HTTPException(400, "no attempts to save")
    path = evaluation.write_results(attempts=body.attempts)
    return {"path": str(path.relative_to(config.ROOT))}

@app.get("/eval/results")
def eval_past_results() -> list[dict]:
    return [{"name": n} for n in evaluation.list_results()]

@app.get("/eval/results/{name}")
def eval_past_result(name: str) -> dict:
    text = evaluation.read_results(name=name)
    if text is None:
        raise HTTPException(404, f"no results file {name!r}")
    return {"name": name, "text": text}
