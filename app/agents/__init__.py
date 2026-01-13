from typing import Literal

from .base_agent import Agent
from .build import agent as build_agent
from .plan import agent as plan_agent

AgentName = Literal["build", "plan"]
AGENTS: dict[AgentName, Agent] = {"build": build_agent, "plan": plan_agent}

__all__ = ["Agent", "AgentName", "AGENTS"]
