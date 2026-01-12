import os
from dataclasses import dataclass
from pathlib import Path

from app.provider import call_api
from app.schemas import Input, ToolSchema
from app.skills.skill import SkillsTool
from app.tools.base_tool import Tool
from app.tools.bash import BashTool
from app.tools.edit import EditTool
from app.tools.glob import GlobTool
from app.tools.grep import GrepTool
from app.tools.read import ReadTool
from app.tools.webfetch import WebFetchTool
from app.tools.write import WriteTool


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


agent = Agent(
    model="gpt-5.2",
    instructions=(Path(__file__).resolve().parent / "agent_prompt.txt")
    .read_text()
    .format(path=os.getcwd()),
    tools={
        "read": ReadTool(),
        "glob": GlobTool(),
        "bash": BashTool(),
        "grep": GrepTool(),
        "edit": EditTool(),
        "write": WriteTool(),
        "webfetch": WebFetchTool(),
        "skills": SkillsTool(),
    },
)
