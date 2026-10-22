# 0014 — The outcome is about what the user got

**Date:** 2026-10-21
**Status:** accepted, waiting for the eval (TEST_PLAN case 84)

## Context

Decision 0013 told the model to leave the cause empty on a good run. After
that, qwen started calling `email-no-tool` a success, 0 times out of 3 right
where it had been 3 out of 3. The agent in that run had no email tool and said
so honestly, and qwen read "the agent did the right thing" as "the task was
done". Nothing the model was told said which of the two the outcome is about.

## Decision

Keep 0013, and add one rule in the same two places the model reads:

1. The `outcome` description in `Report`: judge by what the user got, not by
   whether the agent behaved well.
2. One line in `INSTRUCTIONS` that says it both ways round: an honest "I can't
   do that" still leaves the task undone, and an error the harness logged
   doesn't undo a result the user did get.

## Why

- **Fix the reading, not the case.** The sentence states the rule the cases
  were written with (decision 0012: "judge what the user got"). It doesn't name
  email, birthdays or NO_REPLY, so a better score means the model follows the
  rule, not that it recognises the test.
- **Both ways round,** because the same mistake has a mirror: a run the harness
  marked as an error while the user got exactly the right result
  (`no-reply-in-thinking`, where deepseek and glm both score 0/3).
- **Keep 0013 instead of undoing it.** Its gain for deepseek (cause 0/9 → 6/9)
  is real, and qwen's drop came from a gap the rule leaves open, which this
  fills.

## Consequences

- If qwen's `email-no-tool` comes back and nothing else drops, both decisions
  stay.
- If a model now reads "what the user got" too strictly (NO_REPLY = nothing
  sent = failure), the good runs' outcome scores show it, and the wording
  changes again.
- The next lever after wording is still a code check (0013), not more wording.
