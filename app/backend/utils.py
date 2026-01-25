from pathlib import Path

from app.core import Agent, ProviderProtocol, ToolAny
from app.utils.markdown import MarkdownFrontmatter


def build_agent_from_file(
    path: Path,
    *,
    provider: ProviderProtocol,
    tools_registry: dict[str, ToolAny],
    base_instructions: str = "",
    context: dict[str, str] | None = None,
) -> Agent:
    parsed = MarkdownFrontmatter.from_file(path)
    name = parsed.frontmatter.get("name", path.parent.name)

    if not parsed.has_frontmatter:
        raise ValueError(f"Agent {name} must have frontmatter")

    model = parsed.frontmatter["model"]
    description = parsed.frontmatter.get("description", "")
    tool_names = MarkdownFrontmatter.parse_list(parsed.frontmatter.get("tools", ""))

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

    return Agent(
        name=name,
        model=model,
        description=description,
        instructions=instructions,
        tools=tools,
        provider=provider,
    )
