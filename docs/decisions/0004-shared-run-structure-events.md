# 0004 — The shared run shape: numbered events, previews, pages

**Date:** 2026-10-18
**Status:** accepted

## Context

The investigator (the model, in step 2) needs to read a run. The trace viewer's
answer for one run is OpenClaw-specific and large: a list of messages, each
with blocks (text, thinking, tool call, tool result), where a single tool
result can be 27,000+ characters. Sending all of it at once would fill the
model's context with data it mostly doesn't need, and would tie the
investigator to OpenClaw's field names.

## Decision

Two tools, `get_run` and `get_event` (`app/tools.py`), return the shape in
`app/schema.py`. The model gets JSON, not the viewer's raw answer.

1. **One event per block.** Every message block becomes one numbered event
   of kind `user`, `thinking`, `tool_call`, `tool_result` or `reply`. The
   numbers are how the model points at something ("event 3") and how the
   report will cite evidence. `source_ref` ("message 2, block 0") keeps the
   way back to the viewer's own structure.
2. **Previews, then pages.** `get_run` shows each event as a 200-char preview
   with its full length (`chars`) and `shortened`. `get_event` returns the
   full content in pages of 20,000 chars, with `next_start` for the next page.
   The model sees the whole run's outline cheaply and reads only what it
   chooses.
3. **Only the adapter translates.** `to_overview` and `event_detail` live in
   `app/adapters/openclaw.py`, next to `fetch_run`. The tools and the API
   know only the shared shape. Another trace source would add an adapter,
   not change the tools.
4. **Gaps are said out loud.** A deleted log file gives `events: []` and a
   reason in `missing`; content OpenClaw didn't record is marked
   `not_recorded`; earlier-context messages are marked `prior`. The model is
   never left to guess why something is absent.
5. **Two copies of saved runs.** `scripts/save_run.py` saves a real run to
   `data/` (gitignored, never committed) or, with `--redact`, to
   `tests/fixtures/` with every free text replaced by dots of the same
   length. Tests then use real structure, lengths and paging with no real
   content.

## Why

- Previews + pages bound what each tool call costs, whatever the run's size.
- Numbered events give the report something concrete to cite.
- Keeping translation in the adapter keeps OpenClaw knowledge in one file.

## Consequences

- `/runs/{id}/overview` and `/runs/{id}/events/{n}` show exactly what the
  model will receive, so it can be inspected in a browser.
- Errors became app-level handlers in `main.py` (404 for unknown run or
  event, 503 for viewer down) instead of try/except in each endpoint.
- Each `get_event` call fetches the whole run from the viewer again. Fine at
  this size; caching is a later choice if it becomes slow.
- The event list is flat: which tool_result answers which tool_call is
  inferred from order and tool name, not linked by id.
