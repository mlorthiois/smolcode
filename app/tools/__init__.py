from app.tools.base_tool import Tool
from app.tools.bash import BashTool
from app.tools.edit import EditTool
from app.tools.glob import GlobTool
from app.tools.grep import GrepTool
from app.tools.read import ReadTool
from app.tools.webfetch import WebFetchTool
from app.tools.write import WriteTool
from app.skills.skill import SkillsTool
from app.subagents.subagent import SubAgentTool


TOOLS: dict[str, Tool] = {
    "skills": SkillsTool(),
    "subagent": SubAgentTool(),
    "read": ReadTool(),
    "glob": GlobTool(),
    "grep": GrepTool(),
    "bash": BashTool(),
    "edit": EditTool(),
    "write": WriteTool(),
    "webfetch": WebFetchTool(),
}


__all__ = ["TOOLS", "Tool"]
