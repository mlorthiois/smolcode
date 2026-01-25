import json
from dataclasses import dataclass, field
from typing import cast

from .context import ContextProtocol
from .provider import ProviderProtocol
from .tool import ToolAny, ToolSchema
from .types import (
    AssistantMessage,
    Block,
    FunctionCall,
    FunctionCallOutput,
    Reasoning,
)


@dataclass
class Agent:
    provider: ProviderProtocol
    model: str
    instructions: str
    tools: dict[str, ToolAny] = field(default_factory=dict)
    tools_schema: list[ToolSchema] = field(default_factory=list)
    name: str = ""
    description: str = ""
    tools_registry: dict[str, ToolAny] | None = None

    def __post_init__(self):
        for name, tool in self.tools.items():
            self.tools_schema.append(tool.make_schema(name))

    def _run_tool(self, function_call: FunctionCall) -> tuple[FunctionCallOutput, bool]:
        args = json.loads(function_call["arguments"])

        try:
            tool_output = self.tools[function_call["name"]](args)
            is_success = True
        except Exception as err:
            tool_output = f"error: {err}"
            is_success = False

        return (
            FunctionCallOutput(
                type="function_call_output",
                call_id=function_call["call_id"],
                output=tool_output,
            ),
            is_success,
        )

    def run(self, context: ContextProtocol) -> ContextProtocol:
        while True:
            response = self.provider.call(
                context=context,
                model=self.model,
                instructions=self.instructions,
                tools_schema=self.tools_schema,
            )

            has_tool = False
            for block in response["output"]:
                block = cast(Block, block)

                if block["type"] == "reasoning":
                    reasoning = cast(Reasoning, block)
                    context.add_reasoning(reasoning)
                elif block["type"] == "message":
                    message = cast(AssistantMessage, block)
                    context.add_assistant_message(message)
                elif block["type"] == "function_call":
                    function_call = cast(FunctionCall, block)
                    context.add_function_call(function_call)
                    has_tool = True

                    function_call_output, is_success = self._run_tool(function_call)
                    context.add_function_call_output(
                        function_call, function_call_output, is_success
                    )

            # if no tool output to send back to the model, break the model loop
            if not has_tool:
                return context
