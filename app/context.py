from dataclasses import dataclass

from app.utils.schemas import (
    FunctionCall,
    FunctionCallOutput,
    Input,
    Reasoning,
    UserMessage,
    AssistantMessage,
)
from app.utils.ui import (
    ui_text,
    ui_tool_extract,
    ui_tool_result,
)


@dataclass
class Context(list[Input]):
    # Remove id as `store=False` in codex
    def _add(self, input: Input) -> None:
        if "id" in input:
            del input["id"]  # ty: ignore[invalid-argument-type]
        self.append(input)

    def add_user_message(self, message: UserMessage) -> str:
        self._add(message)
        return message["content"]

    @ui_text(kind="assistant")
    def add_assistant_message(self, message: AssistantMessage) -> str:
        self._add(message)
        return message["content"][0]["text"]

    @ui_text(kind="reasoning")
    def add_reasoning(self, reasoning: Reasoning) -> str:
        self._add(reasoning)
        # Sometimes summary is empty
        if len(reasoning["summary"]) > 0:
            return reasoning["summary"][0]["text"]
        return ""

    @ui_tool_extract
    def add_function_call(self, function_call: FunctionCall) -> FunctionCall:
        self._add(function_call)
        return function_call

    @ui_tool_result
    def add_function_call_output(
        self, function_call_output: FunctionCallOutput, is_success: bool
    ) -> tuple[FunctionCallOutput, bool]:
        self._add(function_call_output)
        return function_call_output, is_success
