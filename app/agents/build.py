import os
from pathlib import Path

from app.skills.skill import SkillsTool
from app.tools.bash import BashTool
from app.tools.edit import EditTool
from app.tools.glob import GlobTool
from app.tools.grep import GrepTool
from app.tools.read import ReadTool
from app.tools.webfetch import WebFetchTool
from app.tools.write import WriteTool

from .base_agent import Agent

base_instructions = (Path(__file__).parent / "prompt" / "base.txt").read_text()
build_instructions = (Path(__file__).parent / "prompt" / "build.txt").read_text()
instructions = base_instructions + build_instructions

agent = Agent(
    model="gpt-5.2",
    instructions=instructions.format(path=os.getcwd()),
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
