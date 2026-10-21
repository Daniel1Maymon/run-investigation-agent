# 0013 — Tell the model to leave the cause empty on a good run

**Date:** 2026-10-21
**Status:** accepted, first version: it helps deepseek and hurts qwen (see Consequences)

## Context

The first full eval run showed that deepseek, the default model, fills in
`suspected_cause` on every good run: "None identified…", "No failure is
evident…", once the text `NULL`, or a note about a harmless oddity. It failed
the cause check on all 9 attempts at the three good runs. qwen and glm mostly
left it empty. The field's only guidance was "or null if none".

## Decision

Say it in both places the model reads:

1. The `suspected_cause` description in `Report` (the `submit_report` schema):
   null when the task succeeded; a harmless oddity goes in the findings.
2. One line in `INSTRUCTIONS` saying the same.

No code check that turns "None"-like text into null.

## Why

- **The model is told in two places**, because a model may lean on the tool
  schema or on the instructions. Saying it once in each costs a line.
- **No text clean-up in code.** A list of "no cause" phrases is endless and
  in two languages, and it would hide the problem instead of fixing it. The
  eval measures whether the wording works.
- **Harmless oddities still have a place.** "OpenClaw logged an error for a
  correct NO_REPLY" is worth reporting, as a finding, not as the cause of a
  failure that didn't happen.

## Consequences

- If the eval shows deepseek still fills it in, the next step is a code check
  in the loop (reject a success report with a cause), not more wording.
- A model might now leave the cause empty on a real failure. The failure
  cases' cause scores watch for that.
- **First result (TEST_PLAN case 82):** deepseek's cause on the good runs went
  from 0/9 to 6/9. But qwen's outcome on `email-no-tool` fell from 3/3 to 0/3:
  it now reads an honest "I can't do that" as success. The old code, run
  again in a separate copy, gave failure 3 times out of 4, so the wording
  caused it. The planned v2 adds one sentence saying the outcome is about what
  the user got, not whether the agent behaved well.
