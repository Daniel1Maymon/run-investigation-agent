# 0007 — The investigation log

Date: 2026-10-18

## Context

An investigation was a black box until it finished: the server printed one
line (`POST …/investigate 200`), and token counts and cost were visible only on
OpenRouter's site. Daniel wants to watch an investigation as it runs, without
drowning in output.

## Decision

1. **One line per thing that happens**, written by the loop, in the server's
   terminal. A typical investigation is about 10 lines:
   - `start`;
   - one `call N` line per model call (seconds, tokens in/out, cost, what the
     model asked for);
   - one `tool` line per tool (ok or error, seconds, size of the answer);
   - a line when something goes wrong (report rejected, cut off, retry, viewer
     down);
   - the end line with the totals.

   Each line starts with the run's first 8 characters.
2. **The loop writes; the adapters report.** Each `ModelReply` carries
   `in_tokens`, `out_tokens`, `cost` and `thinking`; `None` means the provider
   didn't say, and the log shows `?`. The only line an adapter writes is a
   retry, because only the adapter knows a retry happened.
3. **Content stays out of the default log.** The run's content, the model's
   words and its thinking appear only with `LOG_LEVEL=DEBUG`. They are long and
   hold private family data, and the page's report already shows the result.
4. **httpx's own line per request is turned off** (set to WARNING), because our
   lines already cover those calls.
5. **Cost comes from the provider.** OpenRouter returns the price of each call
   (`"usage": {"include": true}`). Claude's API returns tokens but no price, so
   its cost is `?` for now. We don't keep our own price table.

## Why

- **One place.** The loop is the only part that sees the whole story, so the
  log reads in order.
- **Never a wrong total.** If any call's cost is unknown, the total is `?`.
- **Privacy and noise.** Keeping content out at INFO avoids both.

## Consequences

- The thinking is logged once each model call finishes, not word by word. That
  is close to live, because each call takes a few seconds. True word-by-word
  streaming would need `stream: true` and an event stream to the page (a
  bigger change, not done).
- Tested by TEST_PLAN cases 48–50.
