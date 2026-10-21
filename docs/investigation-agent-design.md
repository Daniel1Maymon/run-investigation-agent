# Run Investigation Agent — Basic Design

Version 0.2 · October 19, 2026 · Working direction, open to change

**Status (October 21, 2026):** steps 1 and 2 are built and the first milestone (§8) is reached. Step 3 is partly built: the server log records every step, tokens and cost, but the page does not show tokens and cost yet. Step 4 (evaluation) is built (October 21, 2026): 10 cases from real runs, 3 checks in code, run from `/eval` or `evals/run_eval.py` (decisions 0011, 0012). Step 5 is next. Sections marked *As built* describe the code today; the rest is the original design.

**The goal is to start building and learning. The investigation agent is our current direction, and it can change as we work. Complex agent systems rely on the same building blocks we are learning now; we will develop depth through the challenges we encounter.**

## 1. Purpose

Build an agent that investigates another agent's run: whether the task was completed, what went wrong, and what to check or fix next. It performs work a developer currently does manually: reading the history, inspecting tool calls, and connecting evidence to a diagnosis.

This project is a way to learn agent execution, tools, tracing, monitoring, and evaluation. Success also means being able to explain what we built, why, and how we tested it.

## 2. Initial Scope

- **Source:** OpenClaw runs, using the existing trace viewer.
- **Input:** One manually selected run ID, optionally accompanied by a description of the expected outcome.
- **Output:** A short report with findings, evidence, a suspected cause, and a next step.
- **Permissions:** Read run data only. Suggest fixes without applying them automatically.
- **Later:** Full-session investigations, automatic run selection, and support for additional harnesses.

A run responds to one trigger; a session may contain several runs. Earlier context may be inspected, but must be distinguished from actions performed in the selected run.

## 3. Components

```
  Manual trigger + run ID
          │
          ▼
  Investigation Agent  ◄────►  LLM
     │      │      │
     │      │      └──►  Investigator trace
     │      └─────────►  Evidence-based report
     ▼
  Read-only tools  ─ ─ ─►  Future: other harness adapters
     │
     ▼
  OpenClaw adapter
     │
     ▼
  Existing reader: SQLite + trajectory files
```

These are logical components. The first version can be a single Python program.

*As built:* it is one FastAPI program (`app/`). The agent loop is `app/investigator.py`, one `_Investigation` object per investigation. The LLM is reached through a model adapter (`app/models/`): OpenRouter by default (`deepseek/deepseek-v4.1-flash`), Claude direct also available (decisions 0005, 0006). The adapter reads the trace viewer over HTTP instead of its files (0001). The investigator trace is the server log, one line per step (0007).

| Component | Responsibility |
|---|---|
| Agent loop | Sends context to the model, executes tools, and continues until a report or execution limit is reached |
| LLM | Chooses what to inspect and produces a diagnosis from the returned evidence |
| Tools | Provide defined access to run data |
| Adapter | Translates OpenClaw data into the structure returned by the tools |
| Investigator trace | Records the investigator's own model calls, tool calls, errors, and timings |

## 4. Existing Foundation

In the existing repository, `index_traces.py` maintains a SQLite index, and `load_run()` in `serve.py` reads run details from trajectory files. These capabilities form the starting point for the data access layer.

Define a small shared structure: source, session and run IDs, messages and actions, tool results, recorded status, and source references. Mark missing information explicitly and preserve access to the original data.

This separates investigation logic from the OpenClaw format. A future adapter can support another harness. The shared structure may evolve when we add a second source.

## 5. Initial Tools — Proposed

| Tool | Result |
|---|---|
| `get_run(run_id)` | Run overview: request, recorded status, and messages/actions with IDs and short previews |
| `get_event(run_id, event_id)` | Full content of a selected item, including its source reference |

This separation lets the investigator choose where to look more closely. Responses must indicate when content is shortened or missing.

*As built* (decisions 0004, 0008, 0009): the run is downloaded once when the investigation starts, so the tools take no `run_id`. There are three tools:

| Tool | Result |
|---|---|
| `get_run()` | The run's facts and its numbered events, each as a short preview, with flags for shortened, missing and earlier-context events |
| `get_event(event_id, start)` | The full content of one event, one page at a time, with its source reference |
| `submit_report(report)` | How the model finishes. Its input is the report; its schema is generated from `Report` in `app/schema.py`. An invalid report comes back as a tool error |

## 6. Useful Report

- Outcome: success, failure, or insufficient evidence.
- A finding linked to a message or tool result.
- A clear distinction between recorded facts and suspected causes.
- A practical next step for verification or repair.

*As built:* the report has `outcome`, `summary`, `findings` (each one sentence, the event IDs that show it, and `fact` or `suspicion`), `suspected_cause` and `next_step`. The loop checks it before accepting it, including that every cited event exists.

A tool error does not necessarily mean the task failed. A successful technical status does not prove the user's desired outcome was achieved. Session content is evidence to inspect, not instructions for the investigator to follow.

## 7. Implementation Steps

1. **Data** *(built)*: Save a complete copy of one run and expose it through the two tools. Source files may be trimmed over time; the index alone is not a full-content archive.
2. **First investigation** *(built; limits: 12 model calls, 180 s)*: Connect an agent loop and model, provide a run ID, and produce a report with evidence. Set step and time limits.
3. **Visibility** *(partly built: the server log has every step, tokens and cost; the page doesn't show tokens and cost yet)*: Record the investigator's model and tool calls, errors, duration, token usage, and cost where available.
4. **Evaluation** *(built; 10 cases, decisions 0011 and 0012)*: Test a successful run, a controlled failure, and a case with missing information. Write expected diagnoses beforehand and compare them with the output; do not give those diagnoses to the investigator.
   *As built:* each case is a frozen copy of a real run plus an expected answer written by hand (`evals/cases.json`). The checks are the outcome, the events cited and words in the cause; a good run must name no cause. The cases were picked by reading the investigator's reports on 34 real runs and grouping its mistakes. First full run (October 21, 2026, 3 models × 3 attempts): qwen 81/90 checks, glm 80, deepseek 75. deepseek always names a cause, even on good runs.
5. **Expand when needed:** Add aggregate monitoring and further capabilities in response to problems encountered during development.

If no real failure is available, create a controlled or synthetic test case and label it accordingly. Check whether the investigator identifies the problem, provides evidence, and avoids inventing failures in successful runs.

## 8. First Milestone

**Provide a run ID → the investigator reads data through tools → receive a report with evidence that can be verified against the viewer.**

*Reached:* on October 19, 2026, run `800dfeb3` was investigated live through the tunnel: 8 model calls, outcome success, 8 findings with event IDs, 56.5 s, $0.0077.

Originally still open, now decided: the model and runtime library (our own loop, no agent library, model adapters per provider, OpenRouter by default: 0005, 0006), report presentation (one plain HTML page: 0002) and the data schema (the shared run structure: 0004). Decisions are indexed in `docs/README.md`.

Existing source: [openclaw-trace-viewer](https://github.com/Daniel1Maymon/openclaw-trace-viewer). The existing-code description is based on the repository inspection in this conversation. The parts marked *As built* are implemented and tested (`tests/TEST_PLAN.md`); the rest is the original proposal.
