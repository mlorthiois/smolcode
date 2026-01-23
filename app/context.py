from dataclasses import asdict, dataclass
from typing import Any

from app.schemas import (
    FunctionCall,
    FunctionCallOutput,
    Message,
)
from app.ui import (
    ui_text,
    ui_tool_extract,
    ui_tool_result,
)


@dataclass
class Context(list):
    def add_user_message(self, message: Message) -> str:
        self.append(message)
        return message.content

    @ui_text
    def add_assistant_message(self, message: Message) -> str:
        self.append(message)
        return message.content

    @ui_tool_extract
    def add_function_call(self, function_call: FunctionCall) -> FunctionCall:
        self.append(function_call)
        return function_call

    @ui_tool_result
    def add_function_call_output(
        self, function_call_output: FunctionCallOutput, is_success: bool
    ) -> tuple[FunctionCallOutput, bool]:
        self.append(function_call_output)
        return function_call_output, is_success

    def to_provider_input(self) -> list[dict[Any, Any]]:
        return [asdict(m) for m in self]
