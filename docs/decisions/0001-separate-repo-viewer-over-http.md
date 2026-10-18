# 0001 — Separate repo; read runs through the trace viewer's HTTP API

Date: 2026-10-16

## Context

The agent loop and harness will run inside a FastAPI server. The run data it
needs is already read and reconstructed by the trace viewer
(`openclaw-trace-viewer`), whose `reader.get_run()` is exposed as
`GET /api/run/<id>`. The viewer runs on the Hetzner server next to the
trajectory files.

## Decision

1. The agent is its own repo, not a folder inside the trace viewer.
2. Its OpenClaw adapter reads runs over HTTP from the viewer's
   `/api/run/<id>`, rather than importing or copying `reader.py`.

## Why

- The viewer is standard-library only by design (its `CLAUDE.md`: "If you find
  yourself writing a `requirements.txt`, you have misread the project"). The
  agent needs FastAPI, an LLM SDK and more.
- They are different products that change for different reasons: one lets a
  person look at runs, the other diagnoses them.
- The design plans for other harnesses later. Only the adapter should know
  about OpenClaw.
- HTTP means no copied code: improvements to the viewer's reading reach the
  agent automatically. It also works from the Mac through the same tunnel as
  the dashboard.

## Consequences

- The viewer must be running and reachable (`dash` on the Mac) for the agent to
  read runs. `GET /health` reports whether it is.
- The adapter depends on the shape of the viewer's JSON. If that shape
  changes, the adapter's tests catch it only if they use a recorded real
  response, so keep one as a fixture.
- Importing `reader.py` directly stays possible later, if the agent itself ever
  runs on the server.
