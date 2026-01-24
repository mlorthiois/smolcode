from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal, cast

from app.agent import Agent
from app.tool import Tool

if TYPE_CHECKING:
    from app.skill import Skill


AgentName = Literal["build", "plan"]


def _config_roots() -> list[Path]:
    project_root = Path(__file__).resolve().parent.parent
    repo_config = project_root / "config"
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        xdg_config = Path(xdg_config_home).expanduser() / "smolcode"
    else:
        xdg_config = Path.home() / ".config" / "smolcode"
    return [repo_config, xdg_config]


def _iter_config_files(relative_dir: str, pattern: str) -> list[Path]:
    files: list[Path] = []
    for config_root in _config_roots():
        directory = config_root / relative_dir
        if not directory.exists():
            continue
        files.extend(sorted(directory.glob(pattern)))
    return files


def _config_file(relative_path: str) -> Path | None:
    selected: Path | None = None
    for config_root in _config_roots():
        candidate = config_root / relative_path
        if candidate.exists():
            selected = candidate
    return selected


class Registry:
    _agents: ClassVar[dict[AgentName, Agent] | None] = None
    _subagents: ClassVar[dict[str, Agent] | None] = None
    _skills: ClassVar[dict[str, Skill] | None] = None
    _tools: ClassVar[dict[str, Tool] | None] = None

    @classmethod
    def agents(cls) -> dict[AgentName, Agent]:
        if cls._agents is None:
            agents: dict[AgentName, Agent] = {}
            base_instructions_path = _config_file("agents/common.txt")
            if base_instructions_path is None:
                raise FileNotFoundError("Missing agents/common.txt in config")
            base_instructions = base_instructions_path.read_text()
            context = {"path": os.getcwd()}

            tools_registry = cls.tools()
            for agent_file in _iter_config_files("agents", "*/AGENT.md"):
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
            context = {"path": os.getcwd()}

            tools_registry = cls.tools()
            for subagent_file in _iter_config_files("subagents", "*/SUBAGENT.md"):
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
            from app.skill import Skill

            skills: dict[str, Skill] = {}
            for skill_file in _iter_config_files("skills", "*/SKILL.md"):
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
