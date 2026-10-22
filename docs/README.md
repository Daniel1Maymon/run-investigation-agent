# Docs index

- `investigation-agent-design.md` — the design: purpose, scope, components,
  tools, report, implementation steps; *As built* notes and step status
- `what-we-are-building.md` (+ `.html`) — plain-English picture: all the
  pieces, one investigation step by step, what's next
- `c4-model.html` — the system at the four C4 zoom levels (context,
  containers, components, code). Published copy:
  https://claude.ai/artifact/8NZ41KP1KcdmddX9VsTQ18 — republish it from this
  file when the file changes

All three were last brought up to date on 2026-10-19 (decisions 0001–0010).
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
  - `0009-submit-report-tool.md` — the model hands in its report through a
    `submit_report` tool whose schema is generated from `Report`; an invalid
    report comes back as a tool error
  - `0010-session-list-polls-viewer-version.md` — the session list updates
    itself: the page checks the viewer's data version every 10 s and
    re-fetches the list only when it changed
  - `0011-evaluation-frozen-copies-and-code-checks.md` — the eval grades real
    models on frozen copies of real runs with 3 checks in code (outcome,
    cited events, cause words); a page at `/eval` runs it
  - `0012-first-eval-cases-from-error-analysis.md` — 10 cases picked by
    reading the investigator's reports on 34 real runs; judge what the user
    got, and an empty run is a failure only if it stopped before doing anything
  - `0013-empty-cause-on-good-runs.md` — the model is told, in the schema
    and the instructions, to leave the cause empty when the task succeeded
  - `0014-outcome-is-what-the-user-got.md` — the model is told the outcome
    is about what the user got, not whether the agent behaved well
  - `0015-keep-the-eval-reports.md` — every report the eval produces is saved
    with its steps to the git-ignored `data/eval-reports/`, next to the
    public scores file
