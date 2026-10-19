"""The investigator's tools. Read-only. Each returns plain JSON, the only thing
the model ever sees of a run. See docs/investigation-agent-design.md §5.

The tools know nothing about OpenClaw: the adapter makes the API call
(fetch_run) and translates the answer into the shared shape (to_overview,
event_detail). Errors (RunNotFound, EventNotFound, ViewerUnavailable) are
raised as-is; step 2's agent loop turns them into messages the model can read."""
import httpx

from app.adapters import openclaw

def get_run(client: httpx.Client, run_id: str) -> dict:
    """The run's facts and its numbered events, each as a short preview."""
    raw = openclaw.fetch_run(client=client, run_id=run_id)
    return openclaw.to_overview(raw=raw).model_dump()

def get_event(client: httpx.Client, run_id: str, event_id: int, start: int = 0) -> dict:
    """The full content of one event, PAGE_CHARS at a time."""
    raw = openclaw.fetch_run(client=client, run_id=run_id)
    return openclaw.event_detail(raw=raw, event_id=event_id, start=start).model_dump()
