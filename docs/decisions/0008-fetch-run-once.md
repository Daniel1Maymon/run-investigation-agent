# 0008 — Fetch the run once per investigation

## Context

Both tools (`get_run`, `get_event`) called the viewer's `/api/run/<id>` on
every use and then cut the answer down. The viewer has no endpoint for one
event, and we don't change the viewer (0001), so each call downloaded the
whole run. In run `800dfeb3` that was 11 downloads of the same ~117 KB: one at
the start to count events, then one per tool call.

## Decision

`investigate()` downloads the run once, when the investigation starts, and
keeps it in a local variable (`raw`). The tools take that run and only cut it
down; they make no API call. The copy lives only as long as that one
investigation. The debug endpoints (`/runs/{id}/overview`,
`/runs/{id}/events/{n}`) fetch on each request, as before.

## Why

- One request instead of one per tool call, for the same result.
- The evidence can't change under the model while it works: every tool call
  reads the same snapshot, and the report's event IDs refer to it.
- The tools become pure functions (run in, JSON out), easier to test.

## Consequences

- What the model sees is unchanged (case 51 checks the text is identical).
- A run still in progress is seen as it was when the investigation started.
- The viewer going down mid-investigation no longer stops it; viewer down at
  the start is still a 503 before any model call (case 32 changed). The
  `viewer down during tool` log line is gone (case 50).
