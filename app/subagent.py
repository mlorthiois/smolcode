from dataclasses import dataclass
from typing import TypedDict

from app.agent import Agent
from app.context import Context
from app.tool import Tool
from app.utils.schemas import Input, Message, ToolSchema
from app.utils.ui import pop_depth, push_depth

subagent_description = """\
Delegate a focused subtask to a specialized autonomous subagent. The subagent runs independently and returns a summary of its work.
<available_subagents>{subagents}</available_subagents>
"""


class Args(TypedDict):
    subagent_name: str
    task: str


@dataclass
class SubAgentTool(Tool[Args]):
    """Tool that delegates a task to a specialized subagent."""

    subagents: dict[str, Agent]
    description = subagent_description
    args_type = Args

    def _build_description(self) -> str:
        return subagent_description.format(
            subagents="".join(
                f"<subagent><name>{s.name}</name><description>{s.description}</description></subagent>"
                for s in self.subagents.values()
            )
        )

    def _extract_last_assistant_message(self, ctx: list[Input]) -> str:
        """Extract the last assistant message from context as summary."""
        for item in reversed(ctx):
            if isinstance(item, Message) and item.role == "assistant":
                return item.content
        return "(No response from subagent)"

    def make_schema(self, name: str) -> ToolSchema:
        return ToolSchema(
            name=name,
            description=self._build_description(),
            parameters={
                "type": "object",
                "properties": {
                    "subagent_name": {
                        "type": "string",
                        "description": "Exact identifier of the subagent to use. Must be one of the available subagents.",
                        "enum": list(self.subagents.keys()),
                    },
                    "task": {
                        "type": "string",
                        "description": "The task to delegate to the subagent.",
                    },
                },
                "required": ["subagent_name", "task"],
            },
        )

    def __call__(self, args: Args) -> str:
        subagents = self.subagents
        subagent_name = args["subagent_name"]
        task = args["task"]

        if subagent_name not in subagents:
            return f"error: unknown subagent '{subagent_name}'. Available: {list(subagents.keys())}"

        subagent = subagents[subagent_name]

        # Execute with depth tracking for nested UI
        push_depth()
        try:
            ctx = Context()
            ctx.add_user_message(Message(role="user", content=task))
            subagent.run(ctx)
            summary = self._extract_last_assistant_message(ctx)
        finally:
            pop_depth()

        return summary

    def subagent_names(self) -> list[str]:
        return list(self.subagents.keys())
