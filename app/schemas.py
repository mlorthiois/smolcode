from dataclasses import dataclass
from typing import Any, Literal

Action = Literal["nothing", "conversation", "clear", "switch_agent"]


@dataclass(frozen=True, slots=True)
class UserInputResult:
    action: Action
    feedback: str | None = None


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]
    type: str = "function"


@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class FunctionCall:
    call_id: str
    name: str
    arguments: str
    type: str = "function_call"


@dataclass
class FunctionCallOutput:
    call_id: str
    output: str
    type: str = "function_call_output"


type Input = Message | FunctionCall | FunctionCallOutput
