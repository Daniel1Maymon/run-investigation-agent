"""Claude adapter: the only module that knows the Anthropic API's format."""
import os

import anthropic

from app.models.base import (Message, ModelError, ModelNotConfigured, ModelReply,
                             ToolCall, ToolSpec)

RETRIES = 2


class ClaudeModel:
    def __init__(self, name: str, client: anthropic.Anthropic | None = None,
                 max_tokens: int = 4096):
        # `client` lets tests pass a fake instead of the real API.
        if client is None:
            if not os.environ.get(key="ANTHROPIC_API_KEY"):
                raise ModelNotConfigured(
                    "no ANTHROPIC_API_KEY: put it in .env and start the server with "
                    "`uv run --env-file .env uvicorn app.main:app --reload`")
            client = anthropic.Anthropic(max_retries=RETRIES)
        self.name, self.client, self.max_tokens = name, client, max_tokens

    def next(self, instructions: str, tools: list[ToolSpec],
             history: list[Message], *, timeout: float) -> ModelReply:
        try:
            response = self.client.messages.create(
                model=self.name, max_tokens=self.max_tokens, system=instructions,
                tools=[to_claude_tool(tool=t) for t in tools],
                messages=[to_claude_message(m=m) for m in history],
                # The SDK's timeout is per try: split the budget so all tries fit in it.
                timeout=timeout / (RETRIES + 1))
        except anthropic.APIError as ex:          # a timeout is an APIError too
            raise ModelError(f"model call failed: {ex}") from ex
        return from_claude(response=response)


def to_claude_tool(tool: ToolSpec) -> dict:
    return {"name": tool.name, "description": tool.description,
            "input_schema": tool.parameters}


def to_claude_message(m: Message) -> dict:
    # Claude wants a list of blocks: tool results first, then text, then tool calls.
    # (A message only ever has results or calls, never both.)
    blocks = [{"type": "tool_result", "tool_use_id": r.call_id, "content": r.content,
               "is_error": r.is_error} for r in m.tool_results]
    if m.text:
        blocks.append({"type": "text", "text": m.text})
    blocks += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input}
               for c in m.tool_calls]
    # Claude rejects an empty message; an empty reply is still a turn to keep.
    return {"role": m.role, "content": blocks or [{"type": "text", "text": "(empty)"}]}


def from_claude(response) -> ModelReply:
    usage = getattr(response, "usage", None)
    return ModelReply(
        text="".join(b.text for b in response.content if b.type == "text"),
        tool_calls=[ToolCall(id=b.id, name=b.name, input=b.input)
                    for b in response.content if b.type == "tool_use"],
        cut_off=response.stop_reason == "max_tokens",
        # Claude's API returns tokens but no price, so cost stays unknown.
        in_tokens=getattr(usage, "input_tokens", None),
        out_tokens=getattr(usage, "output_tokens", None))
