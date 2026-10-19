"""OpenRouter adapter: the only module that knows OpenRouter's API format
(the OpenAI "chat completions" format). Plain httpx, no SDK. See docs/decisions/0006."""
import json
import logging
import os
import time

import httpx

from app.models.base import (Message, ModelError, ModelNotConfigured, ModelReply,
                             ToolCall, ToolSpec)

log = logging.getLogger(name=__name__)

URL = "https://openrouter.ai/api/v1/chat/completions"
RETRIES = 2
# Worth trying again: rate limit, the provider behind OpenRouter overloaded or down.
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class OpenRouterModel:
    def __init__(self, name: str, client: httpx.Client | None = None,
                 max_tokens: int = 4096, sleep=time.sleep):
        # `client` and `sleep` let tests pass a fake transport and skip the waits.
        key = os.environ.get(key="OPENROUTER_API_KEY")
        if not key:
            raise ModelNotConfigured(
                "no OPENROUTER_API_KEY: put it in .env and start the server with "
                "`uv run --env-file .env uvicorn app.main:app --reload`")
        self.headers = {"Authorization": f"Bearer {key}", "X-Title": "run-investigation-agent"}
        self.name, self.max_tokens, self.sleep = name, max_tokens, sleep
        self.client = client or httpx.Client()

    def next(self, instructions: str, tools: list[ToolSpec],
             history: list[Message], *, timeout: float) -> ModelReply:
        body = {"model": self.name, "max_tokens": self.max_tokens,
                "usage": {"include": True},                 # tokens and cost (case 49)
                "tools": [to_openrouter_tool(tool=t) for t in tools],
                "messages": [{"role": "system", "content": instructions}]
                            + [m for h in history for m in to_openrouter_messages(m=h)]}
        # Each try gets a third of the budget, so all tries fit in it (case 36).
        per_try = timeout / (RETRIES + 1)
        for attempt in range(RETRIES + 1):
            last = attempt == RETRIES
            try:
                response = self.client.post(url=URL, json=body, headers=self.headers,
                                            timeout=per_try)
            except httpx.TransportError as ex:          # timeouts included
                if last:
                    raise ModelError(f"model call failed: {ex!r}") from ex
                why = type(ex).__name__
            else:
                if response.status_code not in RETRY_STATUS or last:
                    return from_openrouter(data=_ok_json(response=response))
                why = f"HTTP {response.status_code}"
            log.info("retry %d after %s", attempt + 1, why)
            self.sleep(attempt + 1)
        raise AssertionError("unreachable")


def _ok_json(response: httpx.Response) -> dict:
    if response.status_code != 200:
        raise ModelError(f"model call failed: HTTP {response.status_code}: "
                         f"{response.text[:300]}")
    data = response.json()
    # OpenRouter reports a failure of the provider behind it inside a 200.
    if "error" in data or not data.get("choices"):
        raise ModelError(f"model call failed: {data.get('error', data)}")
    return data


def to_openrouter_tool(tool: ToolSpec) -> dict:
    return {"type": "function", "function": {
        "name": tool.name, "description": tool.description, "parameters": tool.parameters}}


def to_openrouter_messages(m: Message) -> list[dict]:
    # One of our messages can become several: each tool result is its own message.
    # This format has no error flag, so an error says so in its text.
    out = [{"role": "tool", "tool_call_id": r.call_id,
            "content": f"Error: {r.content}" if r.is_error else r.content}
           for r in m.tool_results]
    if m.role == "assistant":
        msg = {"role": "assistant", "content": m.text or None}
        if m.tool_calls:
            msg["tool_calls"] = [{"id": c.id, "type": "function", "function": {
                "name": c.name, "arguments": json.dumps(obj=c.input)}} for c in m.tool_calls]
        elif not m.text:
            msg["content"] = "(empty)"      # some providers reject an empty message
        out.append(msg)
    elif m.text or not out:
        out.append({"role": "user", "content": m.text or "(empty)"})
    return out


def from_openrouter(data: dict) -> ModelReply:
    choice = data["choices"][0]
    msg = choice["message"]
    usage = data.get("usage") or {}
    return ModelReply(
        text=msg.get("content") or "",
        tool_calls=[ToolCall(id=c["id"], name=c["function"]["name"],
                             input=_arguments(raw=c["function"].get("arguments")))
                    for c in msg.get("tool_calls") or []],
        cut_off=choice.get("finish_reason") == "length",
        in_tokens=usage.get("prompt_tokens"), out_tokens=usage.get("completion_tokens"),
        cost=usage.get("cost"), thinking=msg.get("reasoning") or "")


def _arguments(raw: str | None) -> dict:
    # Arguments arrive as a JSON string. Broken ones become {}: the loop then tells
    # the model what input is missing, instead of crashing (case 46).
    try:
        parsed = json.loads(s=raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
