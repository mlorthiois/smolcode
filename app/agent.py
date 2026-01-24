import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from app.context import Context
from app.provider import Provider
from app.tool import ToolAny
from app.utils.markdown import MarkdownFrontmatter, parse_list
from app.utils.schemas import FunctionCall, FunctionCallOutput, Message, ToolSchema
from app.utils.ui import require_ui


@dataclass
class Agent:
    provider: Provider
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

    def _call(self, context: Context):
        return self.provider.call(
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
            for block in self._turn(context):
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

    @classmethod
    def from_file(
        cls,
        path: Path,
        *,
        provider: Provider,
        tools_registry: dict[str, ToolAny],
        base_instructions: str = "",
        context: dict[str, str] | None = None,
    ) -> Self:
        parsed = MarkdownFrontmatter.from_file(path)
        name = parsed.frontmatter.get("name", path.parent.name)

        if not parsed.has_frontmatter:
            raise ValueError(f"Agent {name} must have frontmatter")

        model = parsed.frontmatter["model"]
        description = parsed.frontmatter.get("description", "")
        tool_names = parse_list(parsed.frontmatter.get("tools", ""))

        instructions = base_instructions
        if parsed.body:
            if instructions and not instructions.endswith("\n"):
                instructions += "\n"
            instructions += parsed.body

        if context is not None:
            instructions = instructions.format(**context)

        try:
            tools = {tool_name: tools_registry[tool_name] for tool_name in tool_names}
        except KeyError as e:
            raise RuntimeError(f"Tool {e} in Agent:{name} config doesn't exist.")

        return cls(
            name=name,
            model=model,
            description=description,
            instructions=instructions,
            tools=tools,
            provider=provider,
        )
