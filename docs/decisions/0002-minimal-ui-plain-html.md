# 0002 — Minimal UI: one plain HTML page served by the API

Date: 2026-10-17

## Context

Until now the project could only be used by calling its endpoints by hand
(`curl`, or a browser showing raw JSON). We want to see a run, and later the
investigation report, on a page.

## Decision

1. The UI is a single HTML file, `app/ui/index.html`, with its own CSS and
   JavaScript inside it. No framework (React etc.) and no build step.
2. The API serves it at `GET /`. The page calls the API's own
   `GET /runs/{run_id}` from the browser.

## Why

- The page only displays what the API returns. A framework would add a build
  step and a second toolchain for no gain at this size.
- Same server, same address: no second process, and no cross-origin setup.
- Each later phase (tools, report) adds a section to the same page, so the
  progress stays visible.

## Consequences

- The page's JavaScript has no automated tests. Its logic stays thin, and the
  UI cases in `tests/TEST_PLAN.md` are verified live.
- If the UI grows past one page or gets real state, revisit this decision.
