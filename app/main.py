"""The API: health, the session list, one run, the investigator's two tools
(so what the investigator sees can be opened in a browser), and the investigation."""
from collections.abc import Iterator
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from app import investigator, models, tools
from app.adapters import openclaw
from app.models.base import Model, ModelNotConfigured

app = FastAPI(title="Run Investigation Agent")

UI_PAGE = Path(__file__).parent / "ui" / "index.html"


def viewer_client() -> Iterator[httpx.Client]:
    # A dependency, so tests can override it with a fake viewer.
    with openclaw.make_client() as client:
        yield client


def model_client() -> Model:
    # A dependency too, so tests can swap in a fake model.
    return models.make_model()


# One place that turns the adapter's errors into HTTP answers,
# instead of the same try/except in every endpoint.
@app.exception_handler(openclaw.RunNotFound)
@app.exception_handler(openclaw.EventNotFound)
def _not_found(request: Request, ex: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(ex)}, status_code=404)


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
    viewer = openclaw.viewer_status(client)
    return {"status": "ok" if viewer["reachable"] else "degraded", "viewer": viewer}


@app.get("/runs/{run_id}")
def get_run(run_id: str, client: httpx.Client = Depends(viewer_client)) -> dict:
    return openclaw.fetch_run(client, run_id)


@app.get("/runs/{run_id}/overview")
def run_overview(run_id: str, client: httpx.Client = Depends(viewer_client)) -> dict:
    # Exactly what the investigator's get_run tool returns.
    return tools.get_run(client, run_id)


@app.get("/runs/{run_id}/events/{event_id}")
def run_event(run_id: str, event_id: int, start: int = 0,
              client: httpx.Client = Depends(viewer_client)) -> dict:
    # Exactly what the investigator's get_event tool returns.
    return tools.get_event(client, run_id, event_id, start)


@app.post("/runs/{run_id}/investigate")
def investigate_run(run_id: str, client: httpx.Client = Depends(viewer_client),
                    model: Model = Depends(model_client)) -> dict:
    # POST, not GET: it does work (model calls cost money and take time).
    return investigator.investigate(client, model, run_id).model_dump()


@app.get("/sessions")
def list_sessions(client: httpx.Client = Depends(viewer_client)) -> list[dict]:
    # An empty list is a valid answer, so there is no 404 here.
    return openclaw.list_sessions(client)
