"""OpenClaw adapter: reads runs from the trace viewer's HTTP API.

The only module that knows where OpenClaw data comes from. Another harness
would get its own adapter. See docs/decisions/0001.
"""
import httpx

from app import config
from app.schema import Event, EventDetail, RunOverview

PREVIEW_CHARS = 200
PAGE_CHARS = 20_000                 # ≈5k tokens: usually one tool result per page
_NOT_RECORDED = "[not recorded:"    # the viewer's text for content OpenClaw dropped


class RunNotFound(Exception):
    """The viewer has no run with this id. A normal answer, not a failure."""


class ViewerUnavailable(Exception):
    """The viewer could not be reached or answered with an error."""

class EventNotFound(Exception):
    """The run has no event with this id."""


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    # `transport` lets tests swap in a fake viewer.
    return httpx.Client(base_url=config.VIEWER_URL, timeout=config.VIEWER_TIMEOUT,
                        transport=transport)


def _unavailable(detail: str) -> ViewerUnavailable:
    return ViewerUnavailable(
        f"trace viewer at {config.VIEWER_URL} {detail} — is the tunnel open? (run `dash`)")


def fetch_run(client: httpx.Client, run_id: str) -> dict:
    """The run's index row plus its full detail, exactly as the viewer returns it."""
    try:
        r = client.get(url=f"/api/run/{run_id}")
    except httpx.HTTPError as ex:
        raise _unavailable(detail=f"could not be reached ({type(ex).__name__})") from ex
    if r.status_code == 404:
        raise RunNotFound(f"no run with id {run_id!r}")
    if r.status_code != 200:
        raise _unavailable(detail=f"answered HTTP {r.status_code}")
    return r.json()


def viewer_status(client: httpx.Client) -> dict:
    """Whether the viewer answers. Never raises: /health reports, it doesn't crash."""
    status = {"url": config.VIEWER_URL, "reachable": False}
    try:
        r = client.get(url="/api/version")
    except httpx.HTTPError as ex:
        status["error"] = f"could not be reached ({type(ex).__name__})"
        return status
    if r.status_code != 200:
        status["error"] = f"answered HTTP {r.status_code}"
        return status
    status["reachable"] = True
    return status

def data_version(client: httpx.Client) -> int:
    """The viewer's data version: it changes when the viewer indexes new runs. See docs/decisions/0010."""
    try:
        r = client.get(url="/api/version")
    except httpx.HTTPError as ex:
        raise _unavailable(detail=f"could not be reached ({type(ex).__name__})") from ex
    if r.status_code != 200:
        raise _unavailable(detail=f"answered HTTP {r.status_code}")
    return r.json()["v"]

def list_sessions(client: httpx.Client, limit: int = 200) -> list[dict]:
    """The newest sessions, slimmed to what the session list shows. See docs/decisions/0003."""
    try:
        r = client.get(url="/api/runs", params={"limit": limit})
    except httpx.HTTPError as ex:
        raise _unavailable(detail=f"could not be reached ({type(ex).__name__})") from ex
    if r.status_code != 200:
        raise _unavailable(detail=f"answered HTTP {r.status_code}")
    return [_slim_session(row=row) for row in r.json()["rows"]]

def _slim_session(row: dict) -> dict:
    """One session row from /api/runs, cut down to the fields the list needs."""
    failed = row.get("failed") or 0
    return {
        "session_id": row["session_id"],
        "agent": row.get("agent"),
        "started_ts": row.get("started_ts"),
        "status": "failed" if failed else "ok",
        "failed_runs": failed,
        "first_prompt": row.get("user_text") or "",
        "runs": [{"run_id": run["run_id"], "status": run.get("status"),
                  "started_ts": run.get("started_ts")} for run in row.get("runs") or []],
    }

# ---- Translation: the viewer's /api/run answer → the shared shape (app/schema.py) ----

def to_overview(raw: dict) -> RunOverview:
    """The run's facts and its numbered events, each as a preview."""
    detail = raw.get("detail") or {}
    missing = []
    if "error" in detail:  # e.g. the log file was deleted; only the index row is left
        missing.append(f"run detail unavailable: {detail['error']}")
    meta = detail.get("meta") or {}
    return RunOverview(
        source="openclaw",
        run_id=raw["run_id"],
        session_id=raw.get("session_id"),
        agent=raw.get("agent"),
        trigger=raw.get("trigger"),
        model=raw.get("model"),
        recorded_status=raw.get("status"),
        failure_kind=raw.get("failure_kind") or None,
        error_text=raw.get("error_text") or None,
        flags=meta.get("flags") or [],
        started=raw.get("started_ts"),
        ended=raw.get("ended_ts"),
        duration_ms=raw.get("duration_ms"),
        events=[_preview(e=e) for e in _events(detail=detail)],
        missing=missing,
    )

def event_detail(raw: dict, event_id: int, start: int = 0) -> EventDetail:
    """One event's full content, PAGE_CHARS at a time."""
    events = _events(detail=raw.get("detail") or {})
    if not 0 <= event_id < len(events):
        valid = f"0–{len(events) - 1}" if events else "none"
        raise EventNotFound(f"run {raw['run_id']!r} has no event {event_id} "
                            f"(it has {len(events)} events: {valid})")
    e = events[event_id]
    content = e["content"]
    start = max(0, start)
    end = start + PAGE_CHARS
    return EventDetail(
        run_id=raw["run_id"], id=e["id"], kind=e["kind"], tool=e["tool"],
        is_error=e["is_error"], chars=len(content), start=start,
        content=content[start:end],
        next_start=end if end < len(content) else None,
        source_ref=e["source_ref"],
    )

def _events(detail: dict) -> list[dict]:
    """Flatten the viewer's messages into one event per block, keeping the full content."""
    out = []
    for m in detail.get("messages") or []:
        role = m.get("role")
        for bi, b in enumerate(iterable=m.get("blocks") or []):
            kind, tool, content = _classify(role=role, m=m, b=b)
            out.append({
                "id": len(out), "kind": kind, "tool": tool, "content": content,
                "offset_ms": m.get("offset"), "prior": bool(m.get("prior")),
                "is_error": role == "toolResult" and bool(m.get("isError")),
                "source_ref": f"message {m.get('i')}, block {bi}",
            })
    return out

def _classify(role: str, m: dict, b: dict) -> tuple[str, str | None, str]:
    """(kind, tool, content) for one block. OpenClaw's names stop here."""
    if role == "user":
        return "user", None, b.get("text") or ""
    if role == "toolResult":
        return "tool_result", m.get("toolName"), b.get("text") or ""
    if b.get("kind") == "thinking":
        return "thinking", None, b.get("text") or ""
    if b.get("kind") == "toolCall":
        return "tool_call", b.get("name"), b.get("args") or ""
    return "reply", None, b.get("text") or ""

def _preview(e: dict) -> Event:
    c = e["content"]
    return Event(
        id=e["id"], kind=e["kind"], offset_ms=e["offset_ms"], prior=e["prior"],
        tool=e["tool"], is_error=e["is_error"], chars=len(c),
        preview=c[:PREVIEW_CHARS], shortened=len(c) > PREVIEW_CHARS,
        not_recorded=c.startswith(_NOT_RECORDED),
    )
