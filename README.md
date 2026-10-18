# Run Investigation Agent

An agent that investigates another agent's run: was the task completed, what
went wrong, and what to check or fix next. It reports findings with evidence
that can be checked against the trace viewer.

Design: [`docs/investigation-agent-design.md`](docs/investigation-agent-design.md)

## Status

Skeleton. The API reads a run through the OpenClaw adapter; the agent loop,
LLM and tools are next.

```
FastAPI (app/main.py)
  GET /health          is the API up, and can it reach the trace viewer?
  GET /runs/{run_id}   one run, read through the adapter
        │
        ▼
OpenClaw adapter (app/adapters/openclaw.py)
        │ HTTP
        ▼
trace viewer  /api/run/<id>   (on the server, reached through the `dash` tunnel)
```

## Run it

```bash
uv sync
uv run pytest                           # no viewer needed
dash                                    # in another terminal: viewer + tunnel
uv run uvicorn app.main:app --reload    # http://127.0.0.1:8000/docs
```

`VIEWER_URL` (default `http://127.0.0.1:8765`) and `VIEWER_TIMEOUT` (default
`5` seconds) can be set as environment variables.
