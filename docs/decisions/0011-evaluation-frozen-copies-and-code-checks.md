# 0011 — The evaluation: frozen copies of real runs, checks in code, a page to run it

**Date:** 2026-10-20
**Status:** accepted

## Context

The tests prove the loop works with a fake model. They can't say whether a real
model reaches the *right* conclusion about a run, or which of the cheap models
does it best. That needs an evaluation: real models, real runs, known answers.

An eval has three parts. The **dataset** is the inputs, with their expected
answers. The **task** is what the AI does with each input. The **score** says
whether the output was good. Each part had a choice to make.

## Decision

1. **Dataset: frozen copies of real runs.** `evals/snapshot.py` saves the
   viewer's answer for a run once, to `data/eval-runs/<run_id>.json`. It never
   overwrites a copy. The eval reads only these copies, through a fake viewer
   (`httpx.MockTransport`), and never reaches Hetzner.
2. **Expected answers are written by hand** in `evals/cases.json`: the
   outcome, the event ids the report must cite, and words the cause must
   contain (any one of them). Nothing else from the report is graded.
3. **Task: the real `investigate()`, unchanged.** The one addition is that
   `Investigation` now returns its total `cost`, the number the log already
   adds up.
4. **Score: 3 yes/no checks in code.** Outcome equal, every must-cite event
   cited somewhere, and a cause word present (upper/lower case ignored). An
   investigation that doesn't finish fails all three. The table also shows
   average cost and time per model.
5. **Start with one case**: `3178d9f9`, the email request that OpenClaw
   recorded as `success`, though the agent had no email tool.
6. **A page, `/eval`, runs it.** You pick the cases and the models. The
   results are one grid, with cases down the side and models across the top,
   and the reports open on click. The page asks for one attempt per request
   and keeps the tally. When it's done, it asks the server to write the results
   file, and it lists the past results files. `evals/run_eval.py` runs the same
   code from the terminal. The logic lives in `app/evaluation.py`.
7. **Only scores are saved**, to `evals/results/<date>-<time>.md`. The page
   shows the reports, but they are never written to disk.

## Why

- **Frozen copies keep the question fixed.** We grade the investigator, not
  OpenClaw. An old run is still a valid question even if OpenClaw has changed
  since. But the original can disappear: case D in the candidate list existed
  because a trajectory file was deleted. A copy that never changes makes scores
  comparable over time, and the eval works with the tunnel closed.
- **The copies stay out of git** (`data/` is ignored). They hold personal
  messages, and the repo is public. `cases.json` holds only ids and keywords,
  so it is committed.
- **Checks in code first.** Outcome and evidence have one right answer, so code
  can check them exactly. It's cheap, fast and repeatable. Judging the summary
  or next step is subjective and needs an AI judge or a person, so it's left
  for later.
- **Citing the evidence is the quality check.** A right outcome without the
  right event could be a lucky guess.
- **Several cause words**, because the run is in Hebrew and a model may answer
  in Hebrew.
- **This case first** because it is the one the investigator exists for. A
  model that trusts the recorded status gets it wrong.
- **One attempt per request** keeps the server stateless. There are no
  background jobs or progress endpoints, and the page sees each result as it
  arrives. One attempt per model at a time runs the models side by side,
  without sending a burst of requests to one provider.
- **One row per case, not one card per case.** The first layout drew every case
  in full and ran all of them, which stops working beyond a few cases. Details
  open on click, so 50 cases still fit on one screen.
- **Past runs read the saved files**, through endpoints that accept only a
  `<date>-<time>.md` name. They can't be used to read any other file.
- **No report text on disk**, because the reports quote the run.

## Consequences

- A new case is one more line in `cases.json` plus one `snapshot.py` run.
- On a new machine the copies are missing. The page says so, with the command
  to run (409).
- A score of 2/3 is a finding, not a test failure. A failed check means reading
  the report, to see whether the model or the expected answer is wrong.
- Grading the summary and the next step (an AI judge) is the next step after
  more cases.
