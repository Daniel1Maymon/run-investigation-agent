# Docs index

- `investigation-agent-design.md` — the design: purpose, scope, components,
  tools, report, implementation steps
- `what-we-are-building.md` (+ `.html`) — plain-English picture: what the
  skeleton is, all the pieces, which exist yet
- `c4-model.html` — the skeleton drawn at the four C4 zoom levels
  (context, containers, components, code)
- `../tests/TEST_PLAN.md` — every tested behaviour, written before the code
- `decisions/` — why things are the way they are:
  - `0001-separate-repo-viewer-over-http.md` — own repo; runs are read
    through the trace viewer's `/api/run/<id>`
  - `0002-minimal-ui-plain-html.md` — the UI is one plain HTML page served
    by the API at `/`
  - `0003-session-list-slim-adapter-output.md` — the session list: the
    adapter slims `/api/runs` to 7 fields; the page filters in the browser
  - `0004-shared-run-structure-events.md` — the shared run shape: one event
    per block, short previews plus paged full content, only the adapter
    translates, gaps are said out loud
  - `0005-hand-written-model-agnostic-loop.md` — the investigator: our own
    standard loop, a model adapter per provider, report as validated JSON,
    12-call / 180 s limits
  - `0006-openrouter-default-provider.md` — OpenRouter is the default
    model provider (plain httpx adapter); Claude direct stays available
  - `0007-investigation-log.md` — one log line per step in the server's
    terminal; content and thinking only at `LOG_LEVEL=DEBUG`
  - `0008-fetch-run-once.md` — one download of the run per investigation;
    the tools only cut down that copy
