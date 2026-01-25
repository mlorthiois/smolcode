from dataclasses import dataclass
from typing import Any, Literal

# ----------------------------
# User
# ----------------------------
Action = Literal["nothing", "conversation", "clear", "switch_agent", "quit"]


@dataclass(frozen=True, slots=True)
class UserInputResult:
    action: Action
    feedback: str | None = None


# ----------------------------
# Agent
# ----------------------------
@dataclass(frozen=True, slots=True)
class TextEvent:
    text: str
    kind: str = "assistant"


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResultEvent:
    function_name: str
    function_args: str
    content: str
    is_success: bool


@dataclass(frozen=True, slots=True)
class SessionInfoEvent:
    model: str
    tools: tuple[str, ...]
    skills: tuple[str, ...]
    auth: str
    subagents: tuple[str, ...]
    pwd: str
    branch: str


@dataclass(frozen=True, slots=True)
class PromptEvent:
    agent_name: str


@dataclass(frozen=True, slots=True)
class NewlineEvent:
    pass


@dataclass(frozen=True, slots=True)
class SeparatorEvent:
    pass


@dataclass(frozen=True, slots=True)
class DepthEvent:
    delta: int


UIEvent = (
    TextEvent
    | ToolResultEvent
    | SessionInfoEvent
    | PromptEvent
    | NewlineEvent
    | SeparatorEvent
    | DepthEvent
)
