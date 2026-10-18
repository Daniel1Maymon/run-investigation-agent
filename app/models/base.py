"""The model-neutral shapes the investigator's loop speaks.

Every model provider gets an adapter (app/models/<provider>.py) that translates
these to and from its own API format. The loop never sees a provider's format.
See docs/decisions/0005.
"""
from typing import Literal, Protocol

from pydantic import BaseModel


class ToolSpec(BaseModel):
    """A tool, as the model is told about it."""
    name: str
    description: str
    parameters: dict              # JSON Schema of the tool's input


class ToolCall(BaseModel):
    """The model asking for a tool."""
    id: str                       # the provider's id; the answer must quote it
    name: str
    input: dict


class ToolResult(BaseModel):
    """Our answer to one ToolCall."""
    call_id: str
    content: str
    is_error: bool = False


class Message(BaseModel):
    """One entry in the conversation. The history is a list of these."""
    role: Literal["user", "assistant"]
    text: str = ""
    tool_calls: list[ToolCall] = []       # assistant: the tools it asked for
    tool_results: list[ToolResult] = []   # user: our answers to them


class ModelReply(BaseModel):
    """What the model said this turn. No tool calls = it is finished."""
    text: str
    tool_calls: list[ToolCall]
    cut_off: bool = False         # it hit its output limit, so the reply is incomplete


class ModelNotConfigured(Exception):
    """No usable model: missing key or unknown provider."""


class ModelError(Exception):
    """The model call itself failed (network, overload, rate limit…)."""


class Model(Protocol):
    """What every adapter provides. `timeout` is the most seconds one call may
    take, retries included."""
    name: str

    def next(self, instructions: str, tools: list[ToolSpec],
             history: list[Message], *, timeout: float) -> ModelReply: ...
