# Run Investigation Agent

An agent that investigates another agent's run: was the task completed, what
went wrong, and what to check or fix next. It reports findings with evidence
that can be checked against the trace viewer.

Design: [`docs/investigation-agent-design.md`](docs/investigation-agent-design.md)

## Status

Works end to end. Give it a run ID (or press Investigate on the page) and the
model reads the run through three tools and hands in a checked report.
Next: evaluation on runs with known answers. Plain-English overview:
[`docs/what-we-are-building.md`](docs/what-we-are-building.md).

```
page (app/ui/index.html)  ──►  FastAPI (app/main.py)
                                 POST /runs/{id}/investigate
                                      │
                                      ▼
                         agent loop (app/investigator.py)  ◄──►  model adapter (app/models/)
                           │  tools: get_run, get_event,          OpenRouter by default
                           │         submit_report
                           ▼
                OpenClaw adapter (app/adapters/openclaw.py)
                           │ HTTP, fetched once per investigation
                           ▼
                trace viewer /api/run/<id>   (on the server, through the `dash` tunnel)
```

## Run it

```bash
uv sync
uv run pytest                           # no viewer needed
dash                                    # in another terminal: viewer + tunnel
uv run --env-file .env uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

`.env` holds `OPENROUTER_API_KEY` (gitignored); without it the API runs but
can't investigate.

Settings are environment variables, all with defaults: `VIEWER_URL`
(`http://127.0.0.1:8765`), `VIEWER_TIMEOUT` (5 s), `MODEL_PROVIDER`
(`openrouter`), `INVESTIGATOR_MODEL` (`deepseek/deepseek-v4.1-flash`),
`INVESTIGATOR_MAX_STEPS` (12), `INVESTIGATOR_MAX_SECONDS` (180), `LOG_LEVEL`
(`INFO`). See `app/config.py`.
