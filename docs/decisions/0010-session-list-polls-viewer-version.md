# 0010 — The session list updates itself by polling the viewer's data version

**Date:** 2026-10-19
**Status:** accepted

## Context

The page loaded `/sessions` once, the first time the menu opened (0003), and
kept that copy. A session that started later was on our server but not on the
page, while the trace viewer's own page showed it. The only way to see it was
reloading the page.

The viewer already has a cheap change signal: `/api/version` returns `v`, a
number its background sweep (every 30 s) raises when it indexes new runs.
Its own page asks for it every 5 s and reloads its list only when `v` changes.

## Decision

Do the same. The adapter gets `data_version`, our API exposes it as
`GET /sessions/version`, and the page asks it every 10 s. When `v` differs from
the last answer and the list has been loaded, the page fetches `/sessions`
again and redraws it, keeping the search text and scroll position.

- **Poll a version, not the list.** The version answer is a few bytes; the
  list is up to 200 sessions. The list is only re-fetched when it changed.
- **Don't redraw under the reader.** If a session's runs are expanded, the
  page shows a "New sessions" line instead; clicking it redraws.
- **Hidden tab: no checks.** Nothing to update for nobody.
- **Don't trigger the sweep.** The viewer's `POST /api/reindex` would make
  new runs appear sooner, but it makes the viewer do work on our request.
  This project only reads from the viewer (CLAUDE.md), so we wait for its
  own timer.
- **10 s, not 5 s.** The viewer only changes every 30 s at most; checking
  more often than that mainly adds requests.

## Consequences

- A new session shows up within about 40 s (≤30 s sweep + ≤10 s check),
  without a reload.
- One small request every 10 s while the tab is visible, through the tunnel.
- If the viewer restarts, `v` starts again from 0. That differs from the last
  answer, so the page reloads the list once — harmless.
- Checks that fail (viewer down) are ignored silently; the list keeps what it
  had and updates once the viewer answers again.
