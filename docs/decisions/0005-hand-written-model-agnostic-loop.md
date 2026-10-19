# 0005 — The investigator: a hand-written, model-agnostic agent loop

**Date:** 2026-10-18
**Status:** accepted

## Context

Step 2 connects a model to the two tools (decision 0004) so it can investigate
a run and write a report. Options: Anthropic's Claude Agent SDK (a ready-made
agent with a hidden loop and powerful built-in tools), a multi-provider library
(e.g. LiteLLM), or our own loop. The project is for learning agent execution,
must stay read-only, and should not be tied to one model provider.

## Decision

1. **We write the loop ourselves** (`app/investigator.py`), and it is the
   **standard** loop: ask the model; if the reply has tool calls, run them and
   send the answers back; if it has none, the model is finished.
2. *(Replaced by 0009: the report is now handed in through a `submit_report`
   tool.)* **The final answer must be the report as JSON.** The loop validates it
   (`Report` in `app/schema.py`: shape, and every cited event must exist). An
   invalid answer is sent back with what is wrong, and the model tries again.
3. **Model-agnostic through an adapter.** The loop speaks only our own shapes
   (`app/models/base.py`: `Message`, `ToolCall`, `ToolResult`, `ModelReply`).
   `app/models/claude.py` is the only file that knows Claude's format, and it
   uses the plain Anthropic SDK (one request, one reply). Another provider = one
   more adapter. Same pattern as the OpenClaw adapter for runs.
4. **The loop, not the model, chooses the run.** The tools the model sees take
   no run id; the loop fills in the run being investigated.
5. **Limits:** 12 model calls and 180 seconds. Reaching either returns
   `status: "stopped"` with the reason and no report, never a guessed answer.
   Each model call is given only the seconds left, retries included (the
   Claude adapter splits them across its 1 try + 2 retries).
6. **Errors the model can fix go back to it** (unknown event, bad input,
   invalid report, a reply cut off at the length limit: "send a shorter
   report"). **Errors it can't fix stop the investigation**: viewer down →
   503, no API key → 503. A failed model call returns `status: "error"`
   (200) with the steps done so far, not an HTTP error. An unknown run is a
   404 before any model call.

## Why

- **Learning:** the loop is the core idea; with the Agent SDK it would be hidden.
- **Read-only:** the Agent SDK's strength is shell and file tools we must not have.
- **Small job:** two tools, ~12 turns; we don't need long-task context management.
- **Step 3 (visibility)** is easiest when we own every model call.
- **Report as final JSON** (instead of a special "submit" tool) keeps the
  loop standard and works with any model.

## Consequences

- Amended 2026-10-18 after a review (TEST_PLAN cases 36–39): the time limit
  used to be checked only between turns, so one slow call with retries could
  run ~6 minutes; a cut-off reply looked like a plain invalid one; a model
  failure was a bare 502 that lost the steps. Retries were kept rather than
  turned off: brief overloads are common and a retry usually succeeds.
- `stopped` means our limits ended it; `error` means the model call failed.
- `steps` in the result shows what the investigator did; tokens and cost come
  in step 3.
- Tests use a scripted fake model: they prove the loop, not the model's
  judgement. Judgement is checked live against diagnoses written beforehand.
- Comparing with the Agent SDK on the same runs is a possible later experiment.
