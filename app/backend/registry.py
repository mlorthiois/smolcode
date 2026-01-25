import os
from dataclasses import dataclass, field
from typing import Literal, cast

from app.core import Agent, ProviderProtocol, ToolAny
from app.plugins.tools import (
    BashTool,
    EditTool,
    GlobTool,
    GrepTool,
    ReadTool,
    SkillsTool,
    SubAgentTool,
    WebFetchTool,
    WriteTool,
)
from app.utils.config import config_file, iter_config_files

from .context import ContextFactory
from .utils import build_agent_from_file

AgentName = Literal["build", "plan"]


@dataclass
class Registry:
    provider: ProviderProtocol
    context_factory: ContextFactory
    tools: dict[str, ToolAny] = field(default_factory=dict)
    subagents: dict[str, Agent] = field(default_factory=dict)
    agents: dict[AgentName, Agent] = field(default_factory=dict)

    def __post_init__(self):
        self.tools = self._load_tools()
        self.subagents = self._load_subagents()
        self.agents = self._load_agents()

    def _load_tools(self) -> dict[str, ToolAny]:
        return {
            "read": ReadTool(),
            "glob": GlobTool(),
            "grep": GrepTool(),
            "bash": BashTool(),
            "edit": EditTool(),
            "write": WriteTool(),
            "webfetch": WebFetchTool(),
            "skills": SkillsTool(),
        }

    def _load_subagents(self) -> dict[str, Agent]:
        subagents: dict[str, Agent] = {}
        context = {"path": os.getcwd()}
        for subagent_file in iter_config_files("subagents", "*/SUBAGENT.md"):
            subagent = build_agent_from_file(
                subagent_file,
                context=context,
                tools_registry=self.tools,
                provider=self.provider,
            )
            subagents[subagent.name] = subagent
        return subagents

    def _load_agents(self) -> dict[AgentName, Agent]:
        agents: dict[AgentName, Agent] = {}
        base_instructions_path = config_file("agents/common.txt")
        if base_instructions_path is None:
            raise FileNotFoundError("Missing agents/common.txt in config")
        base_instructions = base_instructions_path.read_text()
        context = {"path": os.getcwd()}

        for agent_file in iter_config_files("agents", "*/AGENT.md"):
            agent = build_agent_from_file(
                agent_file,
                base_instructions=base_instructions,
                context=context,
                tools_registry={
                    "subagent": SubAgentTool(
                        subagents=self.subagents,
                        context_factory=self.context_factory,
                    ),
                    **self.tools,
                },
                provider=self.provider,
            )
            agents[cast(AgentName, agent.name)] = agent

        return agents
