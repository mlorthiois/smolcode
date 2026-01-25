from typing import Protocol

from .types import (
    AssistantMessage,
    FunctionCall,
    FunctionCallOutput,
    Reasoning,
    UserMessage,
)


class ContextProtocol(Protocol):
    def add_reasoning(self, reasoning: Reasoning) -> None: ...

    def add_user_message(self, message: UserMessage) -> None: ...

    def add_assistant_message(self, message: AssistantMessage) -> None: ...

    def add_function_call(self, function_call: FunctionCall) -> None: ...

    def add_function_call_output(
        self,
        function_call: FunctionCall,
        function_call_output: FunctionCallOutput,
        is_success: bool,
    ) -> None: ...
