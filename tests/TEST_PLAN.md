# Test plan

Written before the code. Each case says what goes in, what should come out, and
how it can fail. "Mocked" means a fake viewer (`httpx.MockTransport`); "live"
means the real viewer through the tunnel.

## Skeleton

### Case 1 — `GET /health` when the viewer is reachable
- **Input:** the viewer answers `GET /api/version` with 200.
- **Expected:** 200, `{"status": "ok", "viewer": {"reachable": true, "url": ...}}`.
- **Verified:** mocked (`test_health.py`) and live.

### Case 2 — `GET /health` when the viewer is down
- **Input:** connecting to the viewer fails (tunnel closed).
- **Expected:** still 200 (the API itself is up), with `"status": "degraded"`,
  `"reachable": false` and an `error` that says what failed. It must not crash or hang.
  Timeout is 5s.
- **Verified:** mocked (`test_health.py`) and live (tunnel closed).

### Case 3 — adapter: fetch a run that exists
- **Input:** `fetch_run("<id>")`; the viewer returns 200 and the run JSON.
- **Expected:** the decoded JSON is returned unchanged (shaping it into the
  shared structure is a later step).
- **Verified:** mocked (`test_openclaw_adapter.py`) and live with a real run id.

### Case 4 — adapter: run not found
- **Input:** the viewer returns 404 `{"error": "no such run"}`.
- **Expected:** `RunNotFound` is raised, with the run id in the message. A
  missing run is a normal answer, not a crash.
- **Verified:** mocked and live (`nope` as the id).

### Case 5 — adapter: viewer unreachable or erroring
- **Input:** connection refused, or the viewer returns 500.
- **Expected:** `ViewerUnavailable` is raised, with a message that says to
  check the tunnel (`dash`).
- **Verified:** mocked.

### Case 6 — `GET /runs/{run_id}` passes the run through
- **Input:** a run id.
- **Expected:** 200 with the run JSON; 404 for an unknown run; 503 when the
  viewer is unreachable.
- **Verified:** mocked (`test_runs.py`) and live.
- **Why it exists:** proves the full path (API → adapter → viewer) before the
  agent loop is built on top of it.

## Minimal UI

One HTML page at `GET /`. It has a run-ID box and a Check button, and calls our
own `GET /runs/{run_id}`. It adds no new server logic: everything it shows
comes from that endpoint.

### Case 7 — `GET /` serves the page
- **Input:** `GET /`.
- **Expected:** 200, `Content-Type: text/html`, and the page contains the
  run-ID input and the Check button.
- **Failure modes:** file missing or wrong path → 500; served as text instead
  of HTML → browser shows source.
- **Verified:** automated (`test_ui.py`) and live (2026-10-17).

### Case 8 — a real run is shown
- **Input:** a real run id typed into the page, Check clicked.
- **Expected:** the page shows agent, status, model, duration, cost, what was
  asked, the reply, and any error text. Status shows success or failure at a
  glance. A "Report" area says the report comes later.
- **Failure modes:** a missing field shows "—" instead of "undefined";
  long or Hebrew text wraps and keeps its direction.
- **Verified live only:** the page logic is JavaScript in the browser, and this
  project has no JS test runner. The logic is kept thin (it only displays what
  `/runs/{id}` returns) so a live check covers it.
- **Verified live 2026-10-17** in Chrome, typing a real failed run id
  (`51bb2e1a…`, "LLM idle timeout"): red status pill, error shown, Hebrew
  and English text wrap correctly. Note: "What was asked" is cut short,
  because the viewer's run list stores a shortened prompt. The full text
  will come from the `get_run` tool in the Data step.

### Case 9 — unknown run id
- **Input:** `nope`, Check clicked.
- **Expected:** a clear "Run not found" message. No crash, no raw JSON.
- **Verified live 2026-10-17:** shows "Run not found: no run has the ID nope."

### Case 10 — viewer unreachable
- **Input:** tunnel closed, a run id, Check clicked.
- **Expected:** "Can't reach the trace viewer — is the tunnel open? (run
  `dash`)". It must not hang: the server gives up after 5 seconds.
- **Verified live 2026-10-17** (tunnel closed): shows "Can't reach the trace
  viewer … is the tunnel open? (run `dash`)".

### Case 11 — empty input
- **Input:** Check clicked with an empty box.
- **Expected:** nothing is sent; the page asks for a run id.
- **Verified live 2026-10-17:** shows "Paste a run ID first."

## Session list

A **Sessions ▾** button next to Check opens a drop-down menu of the newest
sessions (up to 200), each with its status and first prompt. The menu is
hidden until opened, and the list is fetched the first time it opens. Typing
in the box opens the menu and filters it; clicking a session opens its run
and closes the menu; Esc or a click outside closes it. New server pieces: `openclaw.list_sessions` (reads the
viewer's `/api/runs` and slims each row) and `GET /sessions`. See
docs/decisions/0003.

### Case 12 — adapter: sessions are slimmed
- **Input:** the viewer's `/api/runs` returns two sessions: one with no failed
  runs, one with 1 failed run out of 2.
- **Expected:** each becomes `{session_id, agent, started_ts, status,
  failed_runs, first_prompt, runs: [{run_id, status, started_ts}]}`. The first
  is `ok`; the second is `failed` with both runs kept.
- **Failure modes:** a missing prompt shows as `""`, not `None`; viewer down →
  `ViewerUnavailable` pointing at `dash`.
- **Verified:** mocked (`test_openclaw_adapter.py`).

### Case 13 — `GET /sessions`
- **Input:** `GET /sessions`.
- **Expected:** 200 with the slimmed list, newest first; 503 with the `dash`
  hint when the viewer is unreachable.
- **Verified:** mocked (`test_sessions.py`).

### Case 14 — a real viewer answer slims without errors
- **Input:** one real `/api/runs` answer saved as
  `tests/fixtures/api_runs_sample.json`, with every text field (prompts,
  replies, errors) replaced by placeholders. The structure is real; the
  content is not.
- **Expected:** every row slims without an exception; every status is `ok` or
  `failed`; every session has at least one run.
- **Why it exists:** fake data only contains what I thought of. Real rows can
  have nulls or missing fields.
- **Verified:** automated (`test_openclaw_adapter.py`).

### Case 15 — live: the list works on real data
- **Input:** tunnel open, page opened.
- **Expected:** the list shows status and first prompt per session; Hebrew
  reads right-to-left; the session of known failed run `51bb2e1a…` is red;
  typing part of an ID or a prompt word filters; clicking a one-run session
  opens it; clicking a multi-run session shows its runs, and clicking one opens it.
- **Verified live 2026-10-17** in Chrome: 200 sessions loaded, 8 failed (same
  as the viewer). `51bb2e1a` filtered to one red "failed" session; clicking it
  opened the run. `7392f01f` (2 runs) expanded; Run 2 opened `1bfc386f…`.
  Prompt words filter in English ("briefing" → 49 shown) and Hebrew (1 match);
  nonsense shows "No session matches." Hebrew prompts read right-to-left.
- **Menu re-verified live 2026-10-17** after moving the list behind the
  button: hidden on load; the button opens it ("Loading sessions…", then
  the list); clicking a session opened `6b398c4c…` and closed the menu;
  typing opens and filters it; a multi-run session expands without closing
  it; Esc, the button again, and a click outside all close it.
- **Known limits:** only the first 50 matches are drawn (the filter searches
  all 200). Cron prompts start with a long `[cron:<id> <name>]` tag, so the
  readable part is often cut off in the row.

### Case 16 — live: viewer down
- **Input:** tunnel closed, page opened.
- **Expected:** the list area says it can't reach the trace viewer (run
  `dash`); typing a run ID and clicking Check still behaves as in case 10.
- **Verified live 2026-10-17** (tunnel closed): list shows "Can't load the
  session list. … run `dash`"; Check on a real id shows case 10's message.
  Found and fixed here: typing used to replace the list's error with
  "No sessions."; now the error stays until the list loads.

## Data step: the investigator's tools

Two read-only tools, plain Python functions in `app/tools.py`:
`get_run(run_id)` returns the run's facts and its numbered **events** (one per
message block: user, thinking, tool_call, tool_result, reply), each as a
200-char preview; `get_event(run_id, event_id, start)` returns one event's full
content in pages of 20,000 chars. The adapter translates OpenClaw's answer into
the shared shape in `app/schema.py`. Two URLs show exactly what the tools return:
`/runs/{id}/overview` and `/runs/{id}/events/{event_id}`. See docs/decisions/0004.

Fixtures are real runs saved with `scripts/save_run.py --redact`: every free
text is replaced by dots of the same length, so structure, lengths and paging
are real while the content is not. Real copies go to `data/` (not committed).

### Case 17 — a successful run becomes events
- **Input:** fixture of run `92145325` (nunu, success, 1 tool call).
- **Expected:** events in order `user, thinking, tool_call, tool_result,
  thinking, reply`; the tool_call and tool_result name `family_search`; the
  tool_result is 27,108 chars; `recorded_status` "success"; `missing` empty.
- **Verified:** automated (`test_tools.py`).

### Case 18 — a failed run becomes events
- **Input:** fixture of run `51bb2e1a` (assistant, cron, "LLM idle timeout").
- **Expected:** two `tool_call`s to `google_assi`, two `tool_result`s, and a
  last `reply` of 0 chars; `flags` include `idleTimedOut`; `failure_kind`
  "idle timeout"; `error_text` mentions the idle timeout.
- **Verified:** automated (`test_tools.py`).

### Case 19 — previews are short and say so
- **Input:** both fixtures.
- **Expected:** every preview is at most 200 chars; `shortened` is true exactly
  when the content is longer than 200 chars; `chars` is the full length.
- **Verified:** automated.

### Case 20 — `get_event` pages and refuses bad ids
- **Input:** the 27,108-char tool_result of run `92145325`.
- **Expected:** page 1 = 20,000 chars with `next_start` 20000; page 2 = 7,108
  chars with `next_start` None; `source_ref` names the message and block.
  An event id outside the run → `EventNotFound` naming the valid range.
- **Verified:** automated.

### Case 21 — the log file is gone
- **Input:** a run whose `detail` is `{"error": "trajectory file missing: …"}`
  (OpenClaw deleted the log; only the index row is left).
- **Expected:** `events` empty, `missing` explains why, the facts from the
  index row are still there. No crash.
- **Verified:** automated (hand-made input).

### Case 22 — gaps and earlier context are marked
- **Input:** a message marked `prior` by the viewer; a block whose text is the
  viewer's "[not recorded: … chars …]" placeholder.
- **Expected:** the first gives `prior: true`; the second `not_recorded: true`.
- **Verified:** automated (hand-made input).

### Case 23 — the two URLs, and the shared error handling
- **Input:** `/runs/r1/overview`, `/runs/nope/overview`,
  `/runs/r1/events/99`, and both with the viewer down.
- **Expected:** 200 / 404 / 404 / 503. The error handling moves from
  try/except in each endpoint to app-level handlers, so cases 6 and 13 must
  still pass unchanged.
- **Verified:** automated (`test_runs.py`).

### Case 24 — live: the tools on real runs
- **Input:** tunnel open; `/runs/<id>/overview` and `/events/<n>` for runs
  `92145325` and `51bb2e1a`, in the browser.
- **Expected:** event count equals the number of blocks the viewer shows;
  the 27,108-char tool result opens in two pages; the failed run's last
  event is an empty reply after a ~129-second gap.
- **Verified live 2026-10-18** through the tunnel (`/runs/<id>/overview` and
  `/events/3?start=…` on our API, real viewer behind it):
  - `92145325`: 6 events in the expected order, tool result 27,108 chars,
    `recorded_status` "success", `missing` empty. Event 3 came in two pages:
    20,000 chars (`next_start` 20000), then 7,108 (`next_start` None), both
    "message 2, block 0". Event 6 → 404.
  - `51bb2e1a`: 7 events (user, thinking, 2 × tool_call `google_assi`,
    2 × tool_result, reply). The last reply is 0 chars at 156,505 ms, 129 s
    after the last tool result (27,445 ms). Flags `aborted, timedOut,
    idleTimedOut`; `failure_kind` "idle timeout".
  - The live answers match the redacted fixtures event for event, so the
    automated cases 17–20 test the real structure.

## First investigation: the agent loop

`POST /runs/{id}/investigate` runs the investigator: a hand-written, standard
agent loop (`app/investigator.py`). Each turn it asks the model, looks at the
reply (the last message): tool calls → run them, send the answers back, go
again; no tool calls → the model is finished, and its text must be the report
as JSON. The report is checked (shape + only real event numbers); an invalid
one is sent back to be fixed. Limits: 12 model calls, 180 seconds.

The loop never sees a provider's format. It speaks our own shapes
(`app/models/base.py`: `Message`, `ToolCall`, `ToolResult`, `ModelReply`),
and a model adapter translates (`app/models/claude.py`). The model tools take
no run id: the loop fills in the run being investigated. See docs/decisions/0005.

In tests the model is a **fake** that replies from a script, like the fake
viewer. That tests our loop, not the model's judgement: the live case does that.

### Case 25 — the Claude adapter translates both ways
- **Input:** our history (a user text, an assistant text + tool call, a user
  message with tool results) and a Claude-shaped reply (text + tool_use blocks).
- **Expected:** history → Claude's `messages` (tool_use / tool_result blocks
  with matching ids, `input_schema` for tools); Claude's reply → `ModelReply`
  with the text joined and the tool calls listed. No key → `ModelNotConfigured`
  naming `ANTHROPIC_API_KEY`. A Claude API error → `ModelError`.
- **Verified:** automated (`test_claude_adapter.py`), no network.

### Case 26 — happy path
- **Input:** fake model: `get_run` → then a valid JSON report citing events 3, 5.
- **Expected:** `status "done"`, the report returned as sent, 2 model calls,
  steps `get_run` then the final answer. The 2nd model call **received** the
  get_run JSON as a tool result with the same call id.
- **Verified:** automated (`test_investigator.py`).

### Case 27 — the model asks for an event that doesn't exist
- **Input:** fake model: `get_event(99)` → valid report.
- **Expected:** the model got an error result (`is_error`, "no event 99", the
  valid range); the loop went on; `done`. The step shows `ok: false`.
- **Verified:** automated.

### Case 28 — an invalid final answer is sent back
- **Input:** fake model's final answers, in turn: plain text with no JSON;
  JSON missing `next_step`; a report citing event 42 (the run has 6); then a
  valid report wrapped in a ```json fence.
- **Expected:** each invalid one gets a message back saying exactly what is
  wrong; the fenced valid one is accepted; `done` after 4 model calls.
- **Verified:** automated.

### Case 29 — step limit
- **Input:** fake model that asks for `get_run` forever.
- **Expected:** `status "stopped"`, reason "step limit (12 model calls)",
  exactly 12 model calls, no report.
- **Verified:** automated.

### Case 30 — time limit
- **Input:** same fake model; a fake clock that jumps past 180 s after turn 1.
- **Expected:** `stopped`, reason "time limit (180s)", 1 model call.
- **Verified:** automated.

### Case 31 — the run doesn't exist
- **Input:** `investigate("nope")`.
- **Expected:** `RunNotFound` (→ 404) and **zero** model calls: no money
  spent on nothing.
- **Verified:** automated.

### Case 32 — the viewer goes down mid-investigation
- **Input:** the viewer answers the first request, then refuses connections.
- **Expected:** `ViewerUnavailable` (→ 503 with `dash`) stops the loop. It is
  not sent to the model: the model can't fix the tunnel.
- **Verified:** automated.

### Case 33 — the URL and its errors
- **Input:** `POST /runs/ok/investigate` with the fake model; `nope`; viewer
  down; no model configured (no key); the model call fails.
- **Expected:** 200 with the investigation; 404; 503 with `dash`; 503 naming
  `ANTHROPIC_API_KEY`; 200 with `status "error"` and "model call failed" in
  the reason (it was 502 before case 39). `GET` on the same URL → 405.
- **Verified:** automated (`test_runs.py`).

### Case 34 — the page can start an investigation
- **Input:** `GET /`.
- **Expected:** the page calls `/investigate`.
- **Verified:** automated (`test_ui.py`); the button and report display are
  live only (case 35).

### Case 35 — live: real Claude on real runs
Written **before** running, and never shown to the investigator (design §7.4).
- **`51bb2e1a` (assistant, cron, failed).** Expected: outcome `failure`. It
  should say both `google_assi` results were back by ~27 s, and then the model
  produced nothing until ~156 s and was stopped by the idle timeout. Evidence
  should include event 6 (empty reply) and likely 4–5. The *why* the model
  stalled must be a `suspicion`, not a `fact`.
- **`92145325` (nunu, success).** Expected: outcome `success`, with **no
  invented failure**. It should say `family_search` returned results and the
  reply answered, citing events 3 and 5.
- **Also record:** model calls, seconds, whether it opened the 27,108-char
  event (and both pages), and how the page shows the report.
- **Verified live:** 2026-10-18, through the real page in Chrome (real viewer
  through the tunnel, real model through OpenRouter), model
  `deepseek/deepseek-v4.1-flash`. Both **pass**.
  - `92145325`: outcome `success`, with no invented failure. It cites events
    3 and 5 (and 0 and 2). 4 model calls, 19.8 s. It read **both pages** of
    event 3 (`start=20000`). Its two suspicions (the stored tool result ends
    at 27.8; no search after August) are labelled `suspicion`, not `fact`.
  - `51bb2e1a`: outcome `failure`. It cites event 6 (empty reply), the
    results back by ~27 s (events 4–5) and the idle timeout. The stall is the
    suspected cause, not a fact. 4 model calls, 10.2 s. One finding (the
    harness error) cites no event (`events —`), because the error is
    run-level, not an event.
  - The page shows the report: outcome badge, summary, findings with their
    kind and events, cause, next step, and the steps taken.

## Review fixes: the loop's limits and failures

A review of step 2 found four ways the loop can go wrong that the tests above
miss. Each gets a case here before the fix.

### Case 36 — the time limit is a real limit
- **Problem:** the 180 s limit is checked only *before* each model call. A
  call already running is not stopped: with a 60 s timeout and 2 retries, one
  call can take ~3 minutes, so a run could last ~6 minutes.
- **Input:** a fake model that asks for `get_run` forever; a fake clock at 0
  for the first call and 50 for the second; then a fake model whose call fails
  with `ModelError` when the clock is already past 180 s.
- **Expected:** each call is given only the seconds left: the 1st gets 180,
  the 2nd gets 130. The Claude adapter splits that across its tries: each try
  gets `timeout / 3` (1 try + 2 retries), so all three fit in the budget. A
  call that fails because time ran out ends as `stopped`, "time limit (180s)",
  not as `error`.
- **Failure modes:** the timeout is not passed down (the call gets the old
  fixed 60 s); retries are not counted (3 × the budget).
- **Verified:** automated (`test_investigator.py`, `test_claude_adapter.py`).

### Case 37 — a cut-off reply is recognised and asked again, shorter
- **Problem:** a reply can be at most 4,096 tokens. If Claude hits that limit
  mid-report, the API says so (`stop_reason "max_tokens"`), but we ignored it:
  the half report looked "invalid", and the model was not told *why*, so it
  could write the same long report and be cut off again.
- **Input:** a Claude response with `stop_reason "max_tokens"`, and one with
  `"end_turn"`; a fake model whose 1st reply is cut off (half a JSON report),
  then a valid report; another whose 1st reply is cut off **and** holds a
  tool call, then a valid report.
- **Expected:** the adapter marks the first `cut_off: true`, the second
  `false`. The loop tells the model its answer was cut off and to send a
  shorter report; `done` after 2 calls; the step shows `ok: false`, "cut off".
  A tool call inside a cut-off reply is **not** run (its input may be
  incomplete); the history sent back holds the reply's text only, no
  unanswered tool call (Claude rejects one).
- **Failure modes:** the cut-off reply is sent back as plain "invalid"; the
  tool is run with half its input.
- **Verified:** automated.

### Case 38 — the report is the first JSON object, not everything between braces
- **Problem:** the report was found by taking everything from the first `{` to
  the **last** `}`. A brace in a note after the report (`… I skipped event
  {5}.`) made a valid report fail.
- **Input:** final answers: (a) a valid report then `Note: I skipped event
  {5}.`; (b) `Event {3} matters.` then a valid report; (c) a valid report in a
  ```json fence; (d) broken JSON `{"outcome": "success",`; (e) text with no `{`.
- **Expected:** (a), (b), (c) accepted. (d) sent back as "not valid JSON";
  (e) sent back as "no JSON report".
- **Failure modes:** (a) rejected (the old greedy match); (d) told "no JSON
  report" when there is one, just broken.
- **Verified:** automated.

### Case 39 — the model fails mid-run: keep what it did
- **Problem:** if call 3 failed (overload, network), the whole answer was a
  bare 502 and the steps already done were lost.
- **Input:** a fake model: `get_run`, then `get_event(3)`, then its 3rd call
  raises `ModelError("model call failed: overloaded")`.
- **Expected:** `status "error"` (not `stopped`: `stopped` means our own
  limits ended it), the reason is the error message, the steps
  `get_run` and `get_event` are kept, `model_calls` 3 (the failed call
  counts), no report. Through the URL: 200 with that body, not 502 (case 33
  changes). A missing key is still 503: nothing has started then.
- **Verified:** automated (`test_investigator.py`, `test_runs.py`).

## Review fixes: what real models do that the fake never did

The fake model always sent one tool call with empty text. Real models (any
provider, not only Claude) often do more. These cases use the fake model, so
they check the loop for every provider.

### Case 40 — text plus a tool call in one reply
- **Input:** `ask("get_run", text="Let me look.")` → a valid report.
- **Expected:** `done`; the history on call 2 keeps the text **and** the tool
  call in one assistant message.
- **Verified:** automated (`test_investigator.py`).

### Case 41 — several tool calls in one reply
- **Input:** one reply asking `get_event(3)` and `get_event(5)` → a report.
- **Expected:** both answered in ONE user message, in order, each under its
  own call id (Claude rejects a call left unanswered). `done`.
- **Verified:** automated.

### Case 42 — reading a long event page by page
- **Input:** `get_event(3)` → `get_event(3, start=20000)` → a report.
- **Expected:** answer 1 has `next_start` 20000; answer 2 holds the last
  7,108 chars with `next_start` null. `done`.
- **Verified:** automated.

### Case 43 — the model tries to choose the run
- **Input:** `ask("get_run", run_id="other")` → a report.
- **Expected:** the loop still reads run `ok` (6 events); `run_id` is ignored.
- **Verified:** automated.

### Case 44 — bad tool calls go back to the model
- **Input:** unknown tool `delete_run`; `get_event` with no `event_id`;
  `get_event(event_id="abc")`; then a report.
- **Expected:** each gets an `is_error` answer saying what is wrong; the
  steps show `ok: false`; `done`.
- **Verified:** automated.

### Case 45 — the whole conversation is sent every time
- **Input:** `get_run` → `get_event(3)` → a report.
- **Expected:** call 3 receives all 5 earlier messages in order: the task,
  call 1, its answer, call 2, its answer.
- **Verified:** automated.

## A second provider: OpenRouter

The investigation runs on OpenRouter (one key, many models), not straight on
the Anthropic API. A new adapter, `app/models/openrouter.py`, translates our
shapes to OpenRouter's format (the OpenAI "chat completions" format) and back.
The loop does not change: cases 26–45 already test it for any provider.
OpenRouter becomes the default provider; Claude stays available with
`MODEL_PROVIDER=anthropic`. See docs/decisions/0006.

### Case 46 — the OpenRouter adapter translates both ways
- **Input:** the same history as case 25 (a user text, an assistant text +
  tool call, a user message with an error tool result); a tool spec; an
  OpenRouter reply with text + a tool call whose arguments are a JSON string.
- **Expected:**
  - The request starts with our instructions as a `system` message.
  - An assistant tool call becomes `tool_calls` with `type "function"` and its
    input as a JSON **string**.
  - Each tool result becomes its own `role "tool"` message with the same
    `tool_call_id`. This format has no error flag, so an error result's content
    starts with `Error: `.
  - Tools are sent as `{"type": "function", "function": {name, description,
    parameters}}`.
  - The reply becomes a `ModelReply`, with the arguments parsed back into a dict.
  - `finish_reason "length"` → `cut_off: true`; `"stop"` / `"tool_calls"` → `false`.
- **Failure modes:**
  - Tool-call arguments that are not valid JSON (a weak model) → the call is
    kept with input `{}`, so the loop answers "needs event_id" instead of crashing.
  - An empty assistant message must not be sent as `content: ""` with no tool
    calls, because some providers reject it. It is sent as `"(empty)"`, the
    same as Claude.
- **Verified:** automated (`test_openrouter_adapter.py`), with a fake HTTP
  transport and no network.

### Case 47 — OpenRouter errors, retries and the time budget
- **Input:**
  - no `OPENROUTER_API_KEY`;
  - a 429 and then a good reply;
  - three 503s in a row;
  - a 401;
  - a 200 whose body is `{"error": {...}}`, which OpenRouter sends when the
    provider behind it fails;
  - a request timeout;
  - a call with `timeout=180`.
- **Expected:**
  - No key → `ModelNotConfigured` naming `OPENROUTER_API_KEY`.
  - 429, 5xx, a timeout or a network error is retried, up to 2 retries (3
    tries). So 429-then-ok succeeds, and three 503s → `ModelError`.
  - 401 → `ModelError` at once, with no retry: retrying a bad key can't help.
  - An error in a 200 body → `ModelError`.
  - Each try gets `timeout / 3`, like Claude (case 36), so all tries fit in
    the budget. Retries wait a short moment first; tests skip the wait.
  - The request carries `Authorization: Bearer <key>` and the model name.
- **Failure modes:** retrying a 401 three times; a 200 error body crashing
  with a `KeyError`.
- **Verified:** automated.

### Case 33 change
With no key and the default provider, the 503 names `OPENROUTER_API_KEY`.

### Case 35 change
The live case runs on OpenRouter. The expected diagnoses don't change.
Record which model was used.

### Weak tests made strict
- Case 34 now checks the page's real `POST` to `/investigate`, not just the
  word (it is also in a code comment).
- Case 25's "next sends the translated request" now passes a tool and checks
  the tools and the translated tool call actually sent.
- Case 30's fake clock repeats its last time forever, so an extra clock read
  can't break it.

## Step 3 (part 1): a log you can watch

One line for each thing that happens in an investigation, written by the loop
(the only part that sees the whole story), in the server's terminal. The
adapters only *report* token counts, cost and the model's thinking with each
reply; the one line they write is a retry. The run's content and the model's
words are kept out of the default log (they are long and private) and appear
only with `LOG_LEVEL=DEBUG`. The `httpx` library's own line per request is
turned off, so it doesn't double the noise. See docs/decisions/0007.

### Case 48 — the log tells the story of an investigation
- **Input:** the happy path of case 26 with a fake model whose replies carry
  token counts, a cost and some thinking; the log captured at INFO, then at DEBUG.
- **Expected, at INFO**, each line prefixed by the run's id:
  - `start`, with the model and the number of events;
  - one `call N` line per model call, with seconds, tokens in/out, cost, and
    what the model asked for (`→ get_run`, `→ final answer`);
  - one `tool` line per tool, ok or error, with the size of the answer;
  - `done` with the totals: calls, seconds, tokens in/out, cost.
  None of the run's content or the model's thinking is in it.
- **Expected, at DEBUG:** the model's thinking and its text are logged too.
- **Failure modes:** a reply with no token counts (a fake, or a provider that
  doesn't say) crashes the log line. It must show `?` instead. If any call's
  cost is unknown, the total cost is `?`, never a wrong total.
- **Verified:** automated (`test_logs.py`).

### Case 49 — the adapters report tokens, cost and thinking
- **Input:** an OpenRouter reply with `usage` (`prompt_tokens`,
  `completion_tokens`, `cost`) and `message.reasoning`; a Claude reply with
  `usage` (`input_tokens`, `output_tokens`).
- **Expected:** OpenRouter → in, out, cost and thinking filled in. The
  request asks for usage (`"usage": {"include": true}`). Claude → in and out
  filled in, cost unknown (`None`): Claude's API doesn't return a price.
  A reply without `usage` still works (`None`s).
- **Verified:** automated (`test_openrouter_adapter.py`, `test_claude_adapter.py`).

### Case 50 — things going wrong are in the log
- **Input:** case 28 (rejected reports), case 37 (cut off), case 27 (tool
  error), case 29 (step limit), case 39 (model error), case 47 (a 429 retried).
- **Expected:** a line for each, in plain words: `report rejected: <why>`,
  `→ cut off`, `tool get_event(event_id=99)  error: … no event 99`, `stopped: step limit
  (12 model calls)`, `error: model call failed: …`, `retry 1
  after HTTP 429`. The `httpx` logger is at WARNING.
- **Changed by case 51:** the `viewer down during tool` line is gone. No tool
  call reaches the viewer any more, so it can't go down during one; viewer
  down at the start is a 503 before the log's `start` line (case 32).
- **Verified:** automated.

### Live check
- Run one investigation with the server and watch the terminal. Then again
  with `LOG_LEVEL=DEBUG` to see the thinking.
- **Verified live:** 2026-10-18, run `51bb2e1a` through a real server at DEBUG, with
  `deepseek/deepseek-v4.1-flash`: 17 lines in all (4 calls, 6 tools, start, done),
  thinking and the report text shown at DEBUG only. Totals: 9.2 s, in 10,357 /
  out 1,081 tokens, $0.0015.

## Fetch the run once per investigation

Both tools used to download the whole run from `/api/run/<id>` on every call,
then cut it down: 11 downloads of the same ~117 KB for run 800dfeb3 (1 at the
start + 1 `get_run` + 9 `get_event`). Now the loop downloads it once when the
investigation starts and keeps it in a local variable; the tools only cut down
the copy they are given. What the model sees doesn't change. See
docs/decisions/0008.

### Case 51 — one investigation, one call to the viewer
- **Input:** an investigation whose model asks for `get_run`, then
  `get_event` 1, 3, and 3 again with `start`, then answers; the fake viewer
  counts its requests.
- **Expected:** exactly one request, `/api/run/ok`. The tool answers the model
  gets are the same text as `get_run` / `get_event` on that run.
- **Failure modes:** a tool still fetching (more than one request); the cut-down
  changing on the way (different text from before).
- **Verified:** automated (`test_investigator.py`).

### Case 32 — changed: the viewer going down
- **Before:** the viewer answers the first request, then refuses → the
  investigation stopped with `ViewerUnavailable` (503).
- **Now:**
  - viewer down **at the start** → `ViewerUnavailable` (503 with `dash`) and
    **zero** model calls;
  - viewer down **after the start** → no effect; the investigation finishes
    from its copy.
- **Verified:** automated (`test_investigator.py`).

### Live check
- One real investigation of run `800dfeb3` against the real viewer (through
  the tunnel) and the real model, with every request to the viewer counted:
  exactly one `/api/run/<id>`, and a valid report.
- **Verified live:** 2026-10-19, run `800dfeb3`, `deepseek/deepseek-v4.1-flash`:
  9 tool calls, **1** request to the viewer, status `done`. Each tool line in
  the log went from ~0.2 s to 0.0 s.

## The report is handed in through a `submit_report` tool

The model used to finish by writing the report as JSON text, and the shape of
that JSON was typed by hand into the instructions, a second copy of `Report`.
Now the model gets a third tool, `submit_report`, whose input *is* the report.
Its schema is generated from `Report`, so there is one copy. Calling it is how
the model finishes. The loop still checks the report (shape, and real event
IDs); an invalid one is answered as a tool error. See docs/decisions/0009.

### Case 52 — the tool's schema comes from `Report`
- **Input:** the `submit_report` tool spec the model is given.
- **Expected:**
  - Its parameters are `Report`'s JSON schema: the same fields, with the same
    required ones (`outcome`, `summary`, `findings`, `next_step`) and the same
    allowed values for `outcome` and `kind`.
  - `Finding` is written inline: no `$ref` or `$defs` anywhere (not every
    provider follows them).
  - The hints are in the field descriptions (e.g. `kind` explains fact vs
    suspicion).
  - The instructions no longer hold a JSON block, and they name `submit_report`.
- **Failure modes:** a field added to `Report` that the model is never told about.
- **Verified:** automated (`test_investigator.py`).

### Case 53 — a valid `submit_report` finishes the investigation
- **Input:** fake model: `get_run`, then `submit_report` with a valid report
  citing events 3 and 5; also a reply asking for `get_event` **and**
  `submit_report` together.
- **Expected:** `status "done"`, the report returned as sent, 2 model calls,
  steps `get_run` then `submit_report` (ok, "final report"). The report is not
  copied into the step's input (the page would print it twice). When
  `submit_report` comes with another tool in one reply, the other tool runs
  first and the investigation still ends `done` on that reply.
- **Verified:** automated.

### Case 54 — an invalid report is answered as a tool error
- **Input:** `submit_report` calls, in turn: missing `next_step`; citing event
  42 (the run has 6); an empty input `{}` (what the OpenRouter adapter makes
  of broken JSON, case 46); then a valid report.
- **Expected:** each invalid one gets a tool result with `is_error`, the same
  call id, and exactly what is wrong (the missing field; "events [42] that do
  not exist"; "empty report"). The step shows `ok: false` with that reason.
  `done` after 4 model calls.
- **Failure modes:** the loop crashes on `{}`; an invalid report is accepted;
  the reason is not sent back.
- **Verified:** automated.

### Case 55 — a reply with no tool call is not a report
- **Input:** fake model: a text reply holding a valid report as JSON (the old
  way), then `submit_report` with the same report.
- **Expected:** the text is **not** accepted. The model is told to hand the
  report in through `submit_report`; the step shows `ok: false`. `done` after
  2 model calls, on the `submit_report`.
- **Failure modes:** two ways to finish (text accepted too).
- **Verified:** automated.

### Case 56 — the report's content stays out of the INFO log
- **Input:** case 53's happy path, the log at INFO, with a report whose
  summary holds a marker string.
- **Expected:** the call line says `→ submit_report`, with no report content;
  the marker is not in any INFO line. A rejected one logs
  `report rejected: <why>`.
- **Verified:** automated (`test_logs.py`).

### Changed cases
- **Case 26, 28, 37, 40–45, 48, 50, 51:** the fake model now finishes with
  `submit_report` instead of a JSON text reply. What they test is unchanged.
- **Case 28** (an invalid final answer is sent back) is replaced by case 54.
- **Case 37** (cut off): unchanged in behaviour. A cut-off `submit_report` is
  not run (half its input may be missing); the model is asked for a shorter
  report.
- **Case 38** (finding the first JSON object in the text) is retired: there is
  no free-text report to search any more.

### Live check
- One real investigation of run `800dfeb3` with `deepseek/deepseek-v4.1-flash`
  through the tunnel: it finishes with `submit_report`, status `done`, valid
  report.
- **Verified live:** 2026-10-19, run `800dfeb3`, `deepseek/deepseek-v4.1-flash`,
  real viewer through the tunnel: 8 model calls (1 `get_run`, 12 `get_event`,
  then `submit_report` accepted on the first try: no rejected report),
  status `done`, outcome `success`, 8 findings, 56.5 s, $0.0077. The log line
  read `→ submit_report` with no report content.

## The session list updates itself

The page used to load the session list once, the first time the menu opened,
and never again: a session that started later only showed up after a page
reload. Now the page asks a tiny question every 10 seconds: "has the viewer's
data changed?" The viewer already answers it: `/api/version` returns `v`, a
number it raises whenever its 30-second sweep finds new runs. When `v` differs
from the last answer, the page fetches `/sessions` again. New server pieces:
`openclaw.data_version` and `GET /sessions/version`. See docs/decisions/0010.

### Case 57 — adapter: the viewer's data version
- **Input:** the viewer's `/api/version` answers `{"v": 0, ...}`.
- **Expected:** `openclaw.data_version` returns `0`.
- **Failure modes:** viewer unreachable → `ViewerUnavailable` pointing at
  `dash`; viewer answers an error (HTTP 500) → `ViewerUnavailable` naming the
  status.
- **Verified:** mocked (`test_openclaw_adapter.py`).

### Case 58 — `GET /sessions/version`
- **Input:** `GET /sessions/version`.
- **Expected:** 200 with `{"v": 0}`; 503 with the `dash` hint when the viewer
  is unreachable.
- **Verified:** mocked (`test_sessions.py`).

### Case 59 — the page checks for changes
- **Input:** `GET /`.
- **Expected:** the page calls `/sessions/version` on a timer.
- **Why it's thin:** the timer's behaviour runs in the browser; case 60 checks
  it live. This only catches the check being deleted.
- **Verified:** automated (`test_ui.py`).

### Case 60 — live: a new session appears without a reload
- **Input:** tunnel open, page open, Sessions menu loaded once. Then a new
  OpenClaw run happens (a real one; we don't trigger the viewer's sweep, 0010).
- **Expected:**
  - Within ~40 s (viewer sweep ≤30 s + page check ≤10 s) the new session is at
    the top of the list, with no page reload.
  - Whatever is typed in the search box still filters the new list.
  - The list's scroll position is kept.
  - If a session's run list is expanded, the list is **not** redrawn under
    the reader; a "New sessions — click to show" line appears at the top
    instead, and clicking it redraws.
  - While the tab is hidden, no version checks are sent.
  - Viewer down during a check: nothing changes on screen, checks keep going,
    and the list updates once the viewer is back.
- **Verified live:** not yet.
