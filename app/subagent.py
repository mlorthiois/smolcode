from app.context import Context
from app.registry import Registry
from app.schemas import Message, ToolSchema
from app.tool import Tool
from app.ui import pop_depth, push_depth

subagent_description = """\
Delegate a focused subtask to a specialized autonomous subagent. The subagent runs independently and returns a summary of its work.
<available_subagents>{subagents}</available_subagents>
"""


class SubAgentTool(Tool):
    """Tool that delegates a task to a specialized subagent."""

    description = subagent_description
    args = {"subagent_name": "string", "task": "string"}

    def _build_description(self) -> str:
        subagents = Registry.subagents()
        return subagent_description.format(
            subagents="".join(
                f"<subagent><name>{s.name}</name><description>{s.description}</description></subagent>"
                for s in subagents.values()
            )
        )

    def _extract_last_assistant_message(self, ctx: list) -> str:
        """Extract the last assistant message from context as summary."""
        for item in reversed(ctx):
            if isinstance(item, Message) and item.role == "assistant":
                return item.content
        return "(No response from subagent)"

    def make_schema(self, name: str) -> ToolSchema:
        subagents = Registry.subagents()
        return ToolSchema(
            name=name,
            description=self._build_description(),
            parameters={
                "type": "object",
                "properties": {
                    "subagent_name": {
                        "type": "string",
                        "description": "Exact identifier of the subagent to use. Must be one of the available subagents.",
                        "enum": list(subagents.keys()),
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
        subagent_name = args["subagent_name"]
        task = args["task"]

        subagents = Registry.subagents()

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
