import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from app.schemas import Message, ToolSchema
from app.tools import Tool
from app.ui import pop_depth, push_depth


@dataclass
class SubAgentDef:
    name: str
    description: str
    tools: list[str]
    instructions: str

    @classmethod
    def from_file(cls, f: Path) -> Self:
        content = f.read_text().strip()
        name = f.stem

        if not content.startswith("---"):
            raise ValueError(f"Subagent {name} must have frontmatter")

        lines = content.split("\n")
        description = ""
        tools: list[str] = []
        end_frontmatter = 1

        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_frontmatter = i
                break
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip()
            elif line.startswith("tools:"):
                tools_str = line.split(":", 1)[1].strip()
                tools = [t.strip() for t in tools_str.split(",")]

        instructions = "\n".join(lines[end_frontmatter + 1 :]).strip()

        return cls(
            name=name,
            description=description,
            tools=tools,
            instructions=instructions,
        )


def _load_subagents() -> dict[str, SubAgentDef]:
    subagents = {}
    for f in Path(__file__).parent.glob("*.md"):
        subagent = SubAgentDef.from_file(f)
        subagents[subagent.name] = subagent
    return subagents


SUBAGENTS = _load_subagents()

subagent_description = """\
Delegate a focused subtask to a specialized autonomous subagent. The subagent runs independently and returns a summary of its work.
<available_subagents>{subagents}</available_subagents>
"""


class SubAgentTool(Tool):
    """Tool that delegates a task to a specialized subagent."""

    description = subagent_description.format(
        subagents="".join(
            f"<subagent><name>{s.name}</name><description>{s.description}</description></subagent>"
            for s in SUBAGENTS.values()
        )
    )
    args = {"subagent_name": "string", "task": "string"}

    def _extract_last_assistant_message(self, ctx: list) -> str:
        """Extract the last assistant message from context as summary."""
        for item in reversed(ctx):
            if isinstance(item, Message) and item.role == "assistant":
                return item.content
        return "(No response from subagent)"

    def make_schema(self, name: str) -> ToolSchema:
        return ToolSchema(
            name=name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": {
                    "subagent_name": {
                        "type": "string",
                        "description": "Exact identifier of the subagent to use. Must be one of the available subagents.",
                        "enum": list(SUBAGENTS.keys()),
                    },
                    "task": {
                        "type": "string",
                        "description": "The task to delegate to the subagent.",
                    },
                },
                "required": ["subagent_name", "task"],
            },
        )

    def __call__(self, args: dict) -> str:
        # Lazy imports to avoid circular dependency
        from app.agents.base_agent import Agent
        from app.context import Context

        subagent_name = args["subagent_name"]
        task = args["task"]

        if subagent_name not in SUBAGENTS:
            return f"error: unknown subagent '{subagent_name}'. Available: {list(SUBAGENTS.keys())}"

        subagent_def = SUBAGENTS[subagent_name]

        # Create the agent instance
        agent = Agent(
            model="gpt-5.2-codex",
            instructions=subagent_def.instructions.format(path=os.getcwd()),
            tool_names=subagent_def.tools,
        )

        # Execute with depth tracking for nested UI
        push_depth()
        try:
            ctx = Context()
            ctx.add_user_message(Message(role="user", content=task))
            agent.run(ctx)
            summary = self._extract_last_assistant_message(ctx)
        finally:
            pop_depth()

        return summary
