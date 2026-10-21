# 0012 — The first eval cases, picked by error analysis

**Date:** 2026-10-20
**Status:** accepted

## Context

The eval had one case, chosen before anyone had looked at many reports. A
handful of guessed cases tests what we *think* goes wrong. To find what
*actually* goes wrong, the investigator ran once (deepseek) on 34 real runs of
every agent. Each report was read against its run. Most reports were right. The
mistakes fell into a few groups:

1. **Twin runs, opposite answers.** The same reminder cron, where the right
   move is to send nothing. When the agent wrote `NO_REPLY` as its reply, the
   investigator said success. When the agent wrote it only in its thinking,
   OpenClaw logged an error and the investigator said failure, though the user
   saw the same thing.
2. **Empty runs with no fixed rule.** Runs with 0 events and an error got
   failure in one case and "can't tell" in another.
3. **A cause on good runs.** It never left the cause empty: "None identified",
   "No failure is evident", once the text `NULL`.
4. **Citing almost everything**, which the "cited" check can't catch.
5. **Small made-up worries** in a few suspicions.

Its strength: 5 runs recorded as success that didn't do the job were all
called failures.

## Decision

Nine new cases, ten in all. Each tests one thing:

| case | tests |
|---|---|
| `email-no-tool` (had it) | hidden failure under "success" |
| `birthdays-declined` | hidden failure, another agent: it said it's read-only |
| `listening-list-fallback` | half-done job recorded "success": the add failed and it made an ordinary task |
| `no-reply-sent` | twin A: correctly sent nothing, as a reply |
| `no-reply-in-thinking` | twin B: correctly sent nothing, OpenClaw logged an error |
| `empty-recorded-success` | 0 events, recorded success → can't tell |
| `empty-timed-out` | 0 events, file missing, error "request timed out" after 90 s → can't tell |
| `empty-context-overflow` | 0 events, error "context overflow" → failure |
| `reminder-ok` | plain success, nothing went wrong |
| `idle-timeout` | simple failure, the easy baseline |

Two rules for the expected answers:

- **Judge what the user got, not the label.** Twin B is a success: the user got
  exactly what they should (nothing), whatever OpenClaw logged.
- **An empty run: when did it stop?** If the error came *before anything ran*
  (context overflow at the precheck), nothing was done: failure. If it ran for
  a while and then stopped (timed out after 90 s), it may have done things we
  can't see: can't tell. An empty run recorded as success, with nothing else,
  is also "can't tell".

The checks stay as they are. A good run must have an empty cause.

## Why

- **Cases from real mistakes** test the investigator where it actually breaks.
- **Twins in pairs**: one case alone can't show that the same situation gets
  the same answer.
- **`empty-timed-out` was first written as failure.** After the first full
  run, the models said "can't tell" 8 times out of 9. Their reason held up: we
  don't even know what the user asked for. Daniel agreed, and the expected
  answer was changed. `evals/results/2026-10-21-091230.md` was graded with the
  old answer. `no-reply-in-thinking` was reviewed the same way and stays
  success: OpenClaw asked again for a visible `NO_REPLY` and didn't get one, but
  the user got what they should.
- **Strict empty cause.** A report that says "None identified" in the cause
  field puts text where a program reading the report expects nothing. The
  investigator's instructions should be fixed, and the eval shows whether the
  fix worked.
- **The debatable runs are left out.** Example: the agent deleted the task but
  never said so. A case whose right answer we can't agree on grades nothing.

## Consequences

- With today's investigator, good runs will mostly fail the cause check. That
  is the expected finding, and the next fix.
- Over-citing is still not caught. A "don't cite these" list per case is the
  next check to add.
- The 34 reports stay in the scratchpad: they quote personal messages.
