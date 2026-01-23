import os
from pathlib import Path

from .base_agent import Agent

base_instructions = (Path(__file__).parent / "prompt" / "base.txt").read_text()
plan_instructions = (Path(__file__).parent / "prompt" / "plan.txt").read_text()
instructions = base_instructions + plan_instructions

agent = Agent(
    model="gpt-5.2-codex",
    instructions=instructions.format(path=os.getcwd()),
    tool_names=["read", "glob", "grep", "bash", "webfetch", "skills", "subagent"],
)
