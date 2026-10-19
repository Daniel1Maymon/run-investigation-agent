"""The investigator's tools. Read-only. Each returns plain JSON, the only thing
the model ever sees of a run. See docs/investigation-agent-design.md §5.

The tools know nothing about OpenClaw and make no API call. They are given the
run as the viewer returned it (`raw`, from the adapter's fetch_run) and only cut
it down, through the adapter's translation (to_overview, event_detail). The
caller fetches once and reuses it for every tool call: see docs/decisions/0008.
EventNotFound is raised as-is; the agent loop turns it into a message the model
can read."""
from app.adapters import openclaw

def get_run(raw: dict) -> dict:
    """The run's facts and its numbered events, each as a short preview."""
    return openclaw.to_overview(raw=raw).model_dump()

def get_event(raw: dict, event_id: int, start: int = 0) -> dict:
    """The full content of one event, PAGE_CHARS at a time."""
    return openclaw.event_detail(raw=raw, event_id=event_id, start=start).model_dump()
