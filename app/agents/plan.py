import os
from pathlib import Path

from app.skills.skill import SkillsTool
from app.tools.bash import BashTool
from app.tools.glob import GlobTool
from app.tools.grep import GrepTool
from app.tools.read import ReadTool
from app.tools.webfetch import WebFetchTool

from .base_agent import Agent

base_instructions = (Path(__file__).parent / "prompt" / "base.txt").read_text()
plan_instructions = (Path(__file__).parent / "prompt" / "plan.txt").read_text()
instructions = base_instructions + plan_instructions

agent = Agent(
    model="gpt-5.2-codex",
    instructions=instructions.format(path=os.getcwd()),
    tools={
        "read": ReadTool(),
        "glob": GlobTool(),
        "bash": BashTool(),
        "grep": GrepTool(),
        "webfetch": WebFetchTool(),
        "skills": SkillsTool(),
    },
)
