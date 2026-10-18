# 0006 — OpenRouter is the default model provider

Date: 2026-10-18

## Context

The live test (case 35) needs a paid model. A Claude Pro/Max subscription
covers claude.ai and Claude Code, but not calls our own code makes to the
Anthropic API. The only way to run on the subscription is the Claude Agent
SDK / `claude -p`, and that runs Claude Code's loop instead of ours. Decision
0005 rejected that.

## Decision

1. A second adapter, `app/models/openrouter.py`, talks to OpenRouter's
   `/chat/completions` endpoint (the OpenAI format). It is now the default
   (`MODEL_PROVIDER=openrouter`). The default model is
   `deepseek/deepseek-v4.1-flash`, chosen because it is among the cheapest
   paid models that support tool calls; change it with `INVESTIGATOR_MODEL`.
2. Claude stays available directly with `MODEL_PROVIDER=anthropic`.
3. The adapter uses plain `httpx`, not the OpenAI SDK. httpx is already a
   dependency, and the request is a single POST.
4. It handles retries itself, in the same way as the Claude adapter: 2
   retries, each try gets a third of the time budget. It retries on 429, 5xx,
   timeouts and network errors. Anything else fails at once.
5. Translation gaps, and how each is handled:
   - This format has no error flag on a tool result, so an error result's
     text starts with `Error: `.
   - Tool-call arguments arrive as a JSON string. Broken JSON becomes `{}`,
     so the loop asks the model for the missing input instead of crashing.
   - OpenRouter can report a provider failure inside an HTTP 200, so that
     body is treated as a failed call.

## Why

- **One key, many models.** Step 4's evaluation can compare models (Claude,
  Gemini, DeepSeek…) by changing one setting.
- **It tests decision 0005.** A second provider proves the loop really is
  model-agnostic: it is reused unchanged. Cases 26–45 already ran with a fake
  model.
- **Plain httpx** shows exactly what is sent, with no extra dependency.

## Consequences

- `.env` holds `OPENROUTER_API_KEY` instead of `ANTHROPIC_API_KEY`.
- OpenRouter adds a small fee on top of the model's own price, and its
  routing can send the same model to different providers. Record the model
  used for every live result.
- Tested by TEST_PLAN cases 46–47 (no network), by the bad-key path against
  the real API (401 → `ModelError`), and by live case 35 (both runs passed,
  2026-10-18).
