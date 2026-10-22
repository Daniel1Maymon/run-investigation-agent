# 0015 — Keep the eval's reports

**Date:** 2026-10-21
**Status:** accepted

## Context

The eval saved scores only (decision 0011): report text quotes the run, and
the repo is public. Every report was thrown away once it was scored. After
decision 0014, deepseek's cause on `birthdays-declined` fell from 3/3 to 1/3,
and there was no way to read what it wrote. A score says *that* a check
failed, never *why*: a model mistake (no cause given), a check mistake (the
right cause in other words) or a case mistake (decision 0012 changed one
expected answer after reading the reports) all look the same.

## Decision

Every eval run also saves every attempt in full to
`data/eval-reports/<date>-<time>.json`, the same name as its results file.
Per attempt: case, model, attempt number, status and reason, the 3 checks,
cost, seconds, model calls, the report and the steps. `write_results` writes
both files, so the terminal script and the page both save it.

## Why

- **The score is the alarm, the report is the explanation.** Reading the
  reports behind a failed check is how every fix so far was found (0012,
  0013, 0014). Until now that meant re-running the investigator by hand.
- **In `data/`, not in `evals/results/`.** `data/` is git-ignored, like the
  frozen runs in `data/eval-runs/`: the reports quote personal messages. The
  scores stay public; the reports stay on this machine.
- **The steps too.** A wrong report often comes from where the model looked:
  never opening the event that shows the answer. The steps show that; the
  report doesn't.
- **The same name as the results file,** so the scores and the reports of one
  run are easy to put side by side.
- **No git commit in the file.** It would say which code wrote the reports,
  but the eval is often run on uncommitted instruction changes (0013, 0014),
  where the commit would point at the wrong version. The date and the
  decision log say it well enough for now.

## Consequences

- An eval run now leaves a second file, a few hundred KB, only on this
  machine. Older eval runs have no reports and can't get them.
- The page doesn't read the saved reports yet: past runs show scores only.
  Opening the reports behind a past score from the page is a possible next
  step.
- The attempts the page sends back to the server are larger (they carry the
  steps).
