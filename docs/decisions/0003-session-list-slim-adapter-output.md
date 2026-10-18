# 0003 — Session list: the adapter returns a slim list

**Date:** 2026-10-17
**Status:** accepted

## Context

The page offers recent sessions in a drop-down menu (a **Sessions ▾** button
next to Check, hidden until opened), with each session's status and first
prompt. The trace viewer already has this list: `GET /api/runs`
returns the newest 200 sessions, each with ~18 fields plus every run's full
prompt, reply and error text.

## Decision

`openclaw.list_sessions` reads `/api/runs` and returns each session as 7
fields: `session_id, agent, started_ts, status, failed_runs, first_prompt,
runs[{run_id, status, started_ts}]`. Our API exposes it as `GET /sessions`.
The page filters the list itself, in the browser, on every keystroke.

- **Slim, not pass-through.** This is the first time the adapter reshapes
  data (`fetch_run` still passes the run through unchanged). The page needs
  7 fields; passing ~18 plus every reply would send the browser a lot of
  data it never shows and tie the page to OpenClaw's field names. Only the
  adapter knows those names.
- **Status rule:** `failed` if the viewer counted at least one run in the
  session with `ok = 0`; otherwise `ok`.
- **First prompt** is the viewer's session `user_text`, checked against real
  data to equal the first run's prompt. It is stored shortened by the viewer.
- **Filter in the browser,** not a search endpoint: 200 small rows load
  once, and filtering them is instant. A server search only becomes worth it
  if we need more than the newest 200.

## Consequences

- One extra call to the viewer, made the first time the menu opens (not on
  every page load).
- Sessions older than the newest 200 aren't listed; pasting their run ID
  still works.
- Tested with a saved real `/api/runs` answer whose text fields are replaced
  by placeholders (`tests/fixtures/api_runs_sample.json`, TEST_PLAN case 14).
