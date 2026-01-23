import json
from dataclasses import dataclass, field
from typing import Iterator

from app.context import Context
from app.provider import call_api
from app.schemas import (
    FunctionCall,
    FunctionCallOutput,
    Message,
    ToolSchema,
)
from app.tools import TOOLS
from app.tools.base_tool import Tool
from app.ui import (
    require_ui,
)


@dataclass
class Agent:
    model: str
    instructions: str
    tool_names: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.tools: dict[str, Tool] = {}
        self.tools_schema: list[ToolSchema] = []

        for name in self.tool_names:
            if name in TOOLS:
                tool = TOOLS[name]
                self.tools[name] = tool
                self.tools_schema.append(tool.make_schema(name))

    def _call(self, context: Context):
        return call_api(
            context,
            self.model,
            self.instructions,
            self.tools_schema,
        )

    def _extract_message(self, block) -> Message:
        return Message(role="assistant", content=block["content"][0]["text"])

    def _extract_function_call(self, block) -> FunctionCall:
        function_call = FunctionCall(
            call_id=block["call_id"],
            name=block["name"],
            arguments=block.get("arguments", "{}"),
        )
        return function_call

    def _run_tool(self, function_call: FunctionCall) -> tuple[FunctionCallOutput, bool]:
        args = json.loads(function_call.arguments)

        try:
            tool_output = self.tools[function_call.name](args)
            is_success = True
        except Exception as err:
            tool_output = f"error: {err}"
            is_success = False

        return (
            FunctionCallOutput(call_id=function_call.call_id, output=tool_output),
            is_success,
        )

    def _turn(self, context: Context) -> Iterator[Message | FunctionCall]:
        response = self._call(context)
        for block in response["output"]:
            if block["type"] == "message":
                yield self._extract_message(block)
                continue

            if block["type"] == "function_call":
                yield self._extract_function_call(block)
                continue

    def run(self, context: Context) -> Context:
        while True:
            has_tool = False
            for i, block in enumerate(self._turn(context)):
                if isinstance(block, Message):
                    context.add_assistant_message(block)

                if isinstance(block, FunctionCall):
                    function_call = block
                    context.add_function_call(function_call)
                    has_tool = True

                    function_call_output, is_success = self._run_tool(function_call)
                    context.add_function_call_output(function_call_output, is_success)

                require_ui().newline()

            # if no tool output to send back to the model, break the model loop
            if not has_tool:
                return context
