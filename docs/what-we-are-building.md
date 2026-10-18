# What we are building, and what a "skeleton" is

## 1. What a skeleton is

A skeleton is the **smallest version of the project that runs from start to end, but doesn't do the smart part yet.**

Think of building a house. First you put up the frame: walls, doors, and pipes connected to the street. Nobody can live in it yet, but you can walk from the front door to the kitchen, and water comes out of the tap. Only then do you add the furniture.

In our project:
- **The frame** is a small web server that can fetch a run from your trace viewer and hand it back.
- **The furniture** is the AI agent that reads the run and writes a diagnosis. That comes later.

## 2. Why start with a skeleton

When the AI part goes wrong later, we want to know it's the AI and not the plumbing.

The skeleton answers the boring questions first:
1. Can our code reach the trace viewer on the Hetzner server?
2. What happens when the tunnel is closed?
3. What happens when someone asks for a run that doesn't exist?

If these work before the AI arrives, every later bug is easier to find.

## 3. The finished product

You give it **one run ID**. It gives back **a short report**:
- Did the task succeed, fail, or is there not enough evidence?
- What went wrong, pointing at the exact message or tool call.
- What to check or fix next.

It only **reads**. It never changes anything on the server.

## 4. All the pieces, and which ones the skeleton has

```
  You ── run ID ──►  ① Web server (FastAPI)           ✅ skeleton
                          │
                          ▼
                     ② Agent loop                      ⏳ later
                      │        ▲
                      ▼        │
                     ③ LLM (the model that thinks)     ⏳ later
                          │
                          ▼
                     ④ Tools: get_run, get_event       ⏳ later
                          │
                          ▼
                     ⑤ OpenClaw adapter                ✅ skeleton
                          │  HTTP, through the `dash` tunnel
                          ▼
                     Trace viewer on Hetzner           (already exists)

                     ⑥ Report  ◄── written by the agent loop     ⏳ later
                     ⑦ Investigator trace (a log of the agent itself) ⏳ later
```

| # | Piece | What it does, in plain English | Status |
|---|---|---|---|
| ① | Web server | The front door. You send it a request, it sends back an answer. | ✅ skeleton |
| ② | Agent loop | The manager. It asks the model "what next?", runs the tool the model picks, and repeats until there's a report or a limit is hit. | ⏳ later |
| ③ | LLM | The brain. It decides what to look at and writes the diagnosis. | ⏳ later |
| ④ | Tools | The only actions the brain may take: "show me the run" and "show me this one message in full". | ⏳ later |
| ⑤ | OpenClaw adapter | The translator. The only file that knows where OpenClaw data lives and how to fetch it. | ✅ skeleton |
| ⑥ | Report | The answer you read: outcome, evidence, suspected cause, next step. | ⏳ later |
| ⑦ | Investigator trace | A log of what the investigator itself did, so we can check its work. | ⏳ later |

## 5. What the skeleton can do today

It has two addresses (endpoints):

1. **`GET /health`**: "Are you up, and can you reach the trace viewer?"
   - Tunnel open: `{"status": "ok", ...}`
   - Tunnel closed: `{"status": "degraded", ...}`, plus a hint to run `dash`. It doesn't crash.
2. **`GET /runs/<run id>`**: "Give me this run."
   - The run exists: you get it back.
   - The run doesn't exist: a "not found" answer (404).
   - The tunnel is closed: "viewer unavailable" (503), with a hint to run `dash`.

## 6. The files

| File | Job |
|---|---|
| `app/main.py` | The web server and its two endpoints |
| `app/adapters/openclaw.py` | Fetches runs from the trace viewer |
| `app/config.py` | Where the viewer is (`127.0.0.1:8765`) and how long to wait (5 seconds) |
| `tests/` | Checks for the 6 cases in `tests/TEST_PLAN.md`, using a fake viewer |
| `pyproject.toml` | The list of libraries the project needs |

## 7. What comes after the skeleton

These are the steps from the design doc, in order:
1. **Data**: the two tools, `get_run` and `get_event`, plus a saved copy of one real run.
2. **First investigation**: connect the agent loop and a model, give it a run ID, and get a report.
3. **Visibility**: log what the investigator did, how long it took, and what it cost.
4. **Evaluation**: test it on a run that worked, a run that failed, and a run with missing data. We write the expected answers first.
