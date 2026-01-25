from typing import Literal, NotRequired, TypedDict

# ----------------------------------------
# Features
# ----------------------------------------


# ----------------------------------------
# Message History
# ----------------------------------------
class Block(TypedDict):
    type: Literal["message", "reasoning", "function_call", "function_call_output"]


Role = Literal["user", "assistant"]


class UserMessage(TypedDict):
    role: Literal["user"]
    content: str


class MessageContent(TypedDict):
    type: NotRequired[Literal["output_text"]]
    role: Role
    text: str


class AssistantMessage(Block):
    type: Literal["message"]
    content: list[MessageContent]


class ReasoningSummary(TypedDict):
    text: str
    type: Literal["summary_text"]


class Reasoning(Block):
    type: Literal["reasoning"]
    summary: list[ReasoningSummary]


class FunctionCall(Block):
    type: Literal["function_call"]
    arguments: str
    call_id: str
    name: str


class FunctionCallOutput(Block):
    type: Literal["function_call_output"]
    call_id: str
    output: str


Input = UserMessage | AssistantMessage | FunctionCall | FunctionCallOutput | Reasoning
