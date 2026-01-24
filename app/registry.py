from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal, cast

from app.core.agent import Agent
from app.core.tool import Tool


if TYPE_CHECKING:
    from app.skill import Skill


AgentName = Literal["build", "plan"]


class Registry:
    _agents: ClassVar[dict[AgentName, Agent] | None] = None
    _subagents: ClassVar[dict[str, Agent] | None] = None
    _skills: ClassVar[dict[str, Skill] | None] = None
    _tools: ClassVar[dict[str, Tool] | None] = None

    @classmethod
    def agents(cls) -> dict[AgentName, Agent]:
        if cls._agents is None:
            agents: dict[AgentName, Agent] = {}
            agents_dir = Path(__file__).resolve().parent / "agents"
            base_instructions = (agents_dir / "prompt" / "base.txt").read_text()
            context = {"path": os.getcwd()}

            tools_registry = cls.tools()
            for agent_file in agents_dir.glob("*/AGENT.md"):
                agent = Agent.from_file(
                    agent_file,
                    base_instructions=base_instructions,
                    context=context,
                    tools_registry=tools_registry,
                )
                agents[cast(AgentName, agent.name)] = agent

            cls._agents = agents
        return cls._agents

    @classmethod
    def subagents(cls) -> dict[str, Agent]:
        if cls._subagents is None:
            subagents: dict[str, Agent] = {}
            subagents_dir = Path(__file__).resolve().parent / "subagents"
            context = {"path": os.getcwd()}

            tools_registry = cls.tools()
            for subagent_file in subagents_dir.glob("*/SUBAGENT.md"):
                subagent = Agent.from_file(
                    subagent_file,
                    context=context,
                    tools_registry=tools_registry,
                )
                subagents[subagent.name] = subagent

            cls._subagents = subagents
        return cls._subagents

    @classmethod
    def skills(cls) -> dict[str, Skill]:
        if cls._skills is None:
            from app.skill import Skill, list_skill_files

            skills: dict[str, Skill] = {}
            for skill_file in list_skill_files():
                skill = Skill.from_file(skill_file)
                skills[skill.name] = skill
            cls._skills = skills
        return cls._skills

    @classmethod
    def tools(cls) -> dict[str, Tool]:
        if cls._tools is None:
            from app.skill import SkillsTool
            from app.subagent import SubAgentTool
            from app.tools.bash import BashTool
            from app.tools.edit import EditTool
            from app.tools.glob import GlobTool
            from app.tools.grep import GrepTool
            from app.tools.read import ReadTool
            from app.tools.webfetch import WebFetchTool
            from app.tools.write import WriteTool

            tools: dict[str, Tool] = {
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
            cls._tools = tools
        return cls._tools


__all__ = ["AgentName", "Registry"]
