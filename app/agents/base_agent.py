from dataclasses import dataclass

from app.provider import call_api
from app.schemas import Input, ToolSchema
from app.tools.base_tool import Tool


@dataclass
class Agent:
    model: str
    instructions: str
    tools: dict[str, Tool]

    def __post_init__(self):
        self.tools_schema: list[ToolSchema] = []
        for tool_name, tool in self.tools.items():
            self.tools_schema.append(tool.make_schema(tool_name))

    def call(self, messages: list[Input]):
        return call_api(
            messages,
            self.model,
            self.instructions,
            self.tools_schema,
        )
