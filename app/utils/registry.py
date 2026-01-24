import os
from typing import Literal, cast

from app.agent import Agent
from app.provider import Provider
from app.subagent import SubAgentTool
from app.tool import ToolAny
from app.tools import (
    BashTool,
    EditTool,
    GlobTool,
    GrepTool,
    ReadTool,
    SkillsTool,
    WebFetchTool,
    WriteTool,
)
from app.utils.config import config_file, iter_config_files

AgentName = Literal["build", "plan"]


class Registry:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.tools: dict[str, ToolAny] = self._load_tools()
        self.subagents: dict[str, Agent] = self._load_subagents()
        self.agents: dict[AgentName, Agent] = self._load_agents()

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
            subagent = Agent.from_file(
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
            agent = Agent.from_file(
                agent_file,
                base_instructions=base_instructions,
                context=context,
                tools_registry={
                    "subagent": SubAgentTool(subagents=self.subagents),
                    **self.tools,
                },
                provider=self.provider,
            )
            agents[cast(AgentName, agent.name)] = agent

        return agents
