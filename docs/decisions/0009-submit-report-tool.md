# 0009 — The report is handed in through a `submit_report` tool

**Date:** 2026-10-19
**Status:** accepted (replaces point 2 of 0005, "the final answer must be the
report as JSON")

## Context

The model finished by writing the report as JSON text, and the loop parsed it.
The report's shape lived in two places that could drift apart: `Report` in
`app/schema.py` (what the loop checks) and a hand-typed JSON block in
`INSTRUCTIONS` (what the model is told). Change one, forget the other, and
every report is rejected. Writing JSON as free text also fails: in the live run
of `800dfeb3` (2026-10-19) deepseek's first report was broken JSON and cost an
extra model call.

## Decision

1. The model gets a third tool, **`submit_report`**. Its input *is* the
   report. Calling it is how the model finishes.
2. The tool's input schema is **generated from `Report`**
   (`Report.model_json_schema()`, with the nested `Finding` written inline,
   since not every provider follows `$ref`). The hints the model needs ("1–3
   sentences", "a fact is recorded in the run, a suspicion is your inference")
   move into `Field(description=...)` on the classes. The JSON block is removed
   from `INSTRUCTIONS`. `Report` is now the only place the shape is defined.
3. The loop still validates the report: its shape, and that every cited event
   exists, which no schema can express. An invalid report is answered as a
   **tool error** saying what is wrong, so the model fixes it the same way it
   fixes a bad `get_event`.
4. A reply with **no tool call** is no longer a finished report. The model is
   told to hand the report in through `submit_report`, and the loop goes on.
   There is one way to finish, not two.
5. A valid `submit_report` ends the investigation at once, even if the same
   reply asked for other tools too.

## Why

- **One source of truth.** Changing `Report` changes what the model is told.
- **Fewer broken reports.** Tool inputs are structured JSON. Providers fill
  them in, instead of the model hand-writing JSON inside text.
- **Still model-agnostic.** It uses the tool calling every adapter already
  speaks, unlike a provider's "structured output" mode, which differs between
  providers and models.
- 0005 kept the report as text "to keep the loop standard". A finishing tool
  is now a common, well-known agent pattern, and the loop stays the same
  loop: one more tool, and a different way to tell when the model is done.

## Consequences

- A broken JSON input reaches the loop as an empty report (the OpenRouter
  adapter turns broken arguments into `{}`, case 46), and the model is told so.
- The log shows `→ submit_report` without the report's content: content stays
  out of the INFO log (0007).
- The step list shows `submit_report` where it used to say "final answer".
- The free-text parser (`_read_report`, case 38) is gone.
- Whether broken reports really get rarer is checked live, and in step 4 across
  the three models.
