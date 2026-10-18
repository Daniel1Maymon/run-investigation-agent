"""The shared run structure: what the investigator's tools return, whatever
harness the run came from. Only adapters know a harness's own format.
See docs/decisions/0004."""
from typing import Literal

from pydantic import BaseModel

EventKind = Literal["user", "thinking", "tool_call", "tool_result", "reply"]

class Event(BaseModel):
    """One thing that happened in the run, as a preview. get_event has the full content."""
    id: int
    kind: EventKind
    offset_ms: int | None     # time since the run started; None if not recorded
    prior: bool               # True = earlier context in the session, not this run's work
    tool: str | None = None   # tool_call / tool_result: which tool
    is_error: bool = False    # tool_result: the tool itself reported an error
    chars: int                # length of the full content
    preview: str              # the first PREVIEW_CHARS of it
    shortened: bool           # preview is not the whole content
    not_recorded: bool        # the harness threw the content away (too long to record)

class RunOverview(BaseModel):
    source: str                    # which harness: "openclaw"
    run_id: str
    session_id: str | None
    agent: str | None
    trigger: str | None            # "user" or "cron"
    model: str | None
    recorded_status: str | None    # what the harness recorded, NOT proof the task succeeded
    failure_kind: str | None
    error_text: str | None
    flags: list[str]               # e.g. ["aborted", "idleTimedOut"]
    started: str | None
    ended: str | None
    duration_ms: int | None
    events: list[Event]
    missing: list[str]             # what we couldn't read, said out loud

class EventDetail(BaseModel):
    run_id: str
    id: int
    kind: EventKind
    tool: str | None = None
    is_error: bool = False
    chars: int                     # full length
    start: int                     # this page starts here…
    content: str                   # …and holds up to PAGE_CHARS
    next_start: int | None         # where the next page starts; None = end
    source_ref: str                # where it is in the original data, e.g. "message 2, block 0"


# ---- The investigator's output (docs/decisions/0005) ----

class Finding(BaseModel):
    what: str                                  # one sentence
    evidence: list[int]                        # event ids that show it
    kind: Literal["fact", "suspicion"]         # recorded in the run, or the model's guess

class Report(BaseModel):
    """The investigator's final answer, sent as JSON and checked by the loop."""
    outcome: Literal["success", "failure", "insufficient_evidence"]
    summary: str
    findings: list[Finding]
    suspected_cause: str | None = None
    next_step: str

class Step(BaseModel):
    """One thing the investigator did, so the page can show how it got there."""
    tool: str | None                           # None = a final answer (report)
    input: dict = {}
    ok: bool = True                            # False = error / rejected report
    result_chars: int = 0
    note: str | None = None

class Investigation(BaseModel):
    """What POST /runs/{id}/investigate returns."""
    run_id: str
    model: str
    status: Literal["done", "stopped", "error"]   # stopped = our limits; error = the model call failed
    reason: str | None = None                  # why it stopped or failed
    report: Report | None = None               # only when done
    model_calls: int
    seconds: float
    steps: list[Step]
