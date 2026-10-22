# What we are building, and where it stands

*Updated October 19, 2026.*

## 1. What it does

You give it **one run ID**. It gives back **a short report**:
- Did the task succeed, fail, or is there not enough evidence?
- What went wrong, pointing at the exact message or tool call.
- What to check or fix next.

It only **reads**. It never changes anything on the server.

## 2. How we got here: skeleton first

A skeleton is the **smallest version of the project that runs from start to end, but doesn't do the smart part yet.**

Think of building a house. First you put up the frame: walls, doors, and pipes connected to the street. Only then do you add the furniture.

1. **The frame came first:** a small web server that fetches a run from the trace viewer. It answered the boring questions: can we reach the server, what happens when the tunnel is closed, what happens with a wrong run ID.
2. **Then the furniture:** the AI agent that reads the run and writes the report. Because the frame was already tested, every bug since then has been in the new part, not the plumbing.

Both are built now.

## 3. All the pieces

```
  You ── run ID ──►  ① Web server + page (FastAPI)       ✅ built
                          │
                          ▼
                     ② Agent loop                         ✅ built
                      │        ▲
                      ▼        │
                     ③ LLM, through OpenRouter            ✅ built
                          │ asks for tools
                          ▼
                     ④ Tools: get_run, get_event,         ✅ built
                              submit_report
                          │
                          ▼
                     ⑤ OpenClaw adapter                   ✅ built
                          │  HTTP, through the `dash` tunnel
                          ▼
                     Trace viewer on Hetzner              (already existed)

                     ⑥ Report  ◄── handed in by the model, checked by the loop   ✅ built
                     ⑦ Investigator log (what the agent itself did)              ✅ built
```

| # | Piece | What it does, in plain English |
|---|---|---|
| ① | Web server + page | The front door. A page where you pick a run and press Investigate. |
| ② | Agent loop | The manager. It asks the model "what next?", runs the tool the model picks, and repeats until there's a report or a limit is hit (12 model calls or 180 seconds). |
| ③ | LLM | The brain. It decides what to look at and writes the diagnosis. Default: `deepseek/deepseek-v4.1-flash` through OpenRouter. |
| ④ | Tools | The only actions the brain may take: "show me the run", "show me this one event in full", and "here is my report". |
| ⑤ | OpenClaw adapter | The translator. The only file that knows where OpenClaw data lives and how to read it. |
| ⑥ | Report | The answer you read: outcome, summary, findings with event IDs, suspected cause, next step. |
| ⑦ | Investigator log | One line per step in the server's terminal: which tool, how long, tokens, cost. |

## 4. One investigation, step by step

1. You press **Investigate** on a run. The page sends `POST /runs/<id>/investigate`.
2. The server downloads the run from the trace viewer **once**.
3. The agent loop sends the model its instructions and the three tools.
4. The model asks for `get_run`: the list of everything that happened in the run, each as a short preview.
5. It asks for `get_event` on the events that look important, to read them in full.
6. When it has enough evidence, it calls `submit_report`.
7. The loop checks the report: right shape, and every event it points at really exists. If something is wrong, the model is told what and tries again.
8. The page shows the report and the list of steps the agent took.

A real example (run `800dfeb3`, October 19): 8 model calls, 56 seconds, less than one cent.

## 5. What you can ask the server

| Address | What it answers |
|---|---|
| `GET /` | The page |
| `GET /sessions` | The list of recent sessions and their runs (the page refreshes it by itself when new runs arrive) |
| `GET /runs/<id>` | One run, as the viewer has it |
| `POST /runs/<id>/investigate` | Runs an investigation and returns the report and the steps |
| `GET /health` | "Are you up, and can you reach the viewer?" Tunnel closed → "degraded", plus a hint to run `dash` |
| `GET /runs/<id>/overview`, `GET /runs/<id>/events/<n>` | For debugging: exactly what the `get_run` and `get_event` tools give the model |
| `GET /eval` | The eval page: pick cases and models, run them, read past results |
| `GET /eval/cases`, `POST /eval/cases/<id>/attempts` | The cases, and one graded investigation of one case by one model |
| `GET /eval/results`, `POST /eval/results` | The saved results files: list, read one, save a new one |

A wrong run ID gets "not found" (404). A closed tunnel gets "viewer unavailable" (503) with a hint to run `dash`.

## 6. The files

| File | Job |
|---|---|
| `app/main.py` | The web server and its addresses |
| `app/ui/index.html` | The page |
| `app/investigator.py` | The agent loop, its instructions and the three tool descriptions |
| `app/tools.py` | `get_run` and `get_event` |
| `app/schema.py` | The shapes: a run's events, the report, the steps |
| `app/adapters/openclaw.py` | Reads runs from the trace viewer and translates them |
| `app/models/` | One adapter per model provider: OpenRouter, Claude |
| `app/config.py` | Settings: where the viewer is, which model, the limits |
| `app/logs.py` | Where the investigator log goes |
| `app/evaluation.py`, `app/ui/eval.html` | The eval: load the cases, replay a saved run, grade the report, write the results |
| `evals/` | The cases (`cases.json`), the scripts that save a run and run the eval, and the results files |
| `tests/` | 138 automated checks for the cases in `tests/TEST_PLAN.md`, with a fake viewer and a fake model |
| `docs/decisions/` | Why things are the way they are, one file per decision |

## 7. What comes next

The evaluation is built: 10 cases from real runs, each run 3 times on three cheap models, scored by checks in code. What's left:
1. **Fix what the eval found:** the model is told how to judge the outcome and when to leave the cause empty, and the eval is run again to see if it helped.
2. **A stricter cited check:** today every model cites the right events on every case, so the check tells nothing apart. Each case will also list events that should *not* be cited.
3. **Visibility, the rest:** show tokens and cost on the page, not only in the log.
