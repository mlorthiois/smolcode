import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import cast, get_args

from app.backend.context import Context
from app.backend.registry import AgentName, Registry
from app.core import Agent, SessionProtocol
from app.core.types import UserMessage

from .context import ContextFactory
from .events import (
    NewlineEvent,
    PromptEvent,
    SeparatorEvent,
    SessionInfoEvent,
    TextEvent,
    UIEvent,
    UserInputResult,
)
from .protocols import InputProvider


@dataclass
class Session(SessionProtocol):
    current_agent_name: AgentName
    registry: Registry
    context_factory: ContextFactory
    input_provider: InputProvider
    context: Context = field(init=False)

    def __post_init__(self) -> None:
        self.context = self.context_factory.root()

    def get_agent(self) -> Agent:
        return self.registry.agents[self.current_agent_name]

    def _emit_action_feedback(self, result: UserInputResult) -> None:
        if result.action not in ("nothing", "quit"):
            self._emit(SeparatorEvent())

        if result.feedback is None:
            return

        kind = "status" if result.action in ("clear", "switch_agent") else "assistant"
        self._emit(TextEvent(result.feedback, kind=kind))

    def _emit_session_info(self) -> None:
        skills = tuple(
            self.get_agent()
            .tools["skills"]
            .make_schema("skills")
            .parameters["properties"]["skill_name"]["enum"]
        )
        tools = tuple(self.get_agent().tools.keys())
        branch = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True
        ).stdout.strip()

        self._emit(
            SessionInfoEvent(
                model=self.get_agent().model,
                skills=skills,
                tools=tools,
                auth=self.registry.provider.auth_mode(),
                subagents=tuple(self.registry.subagents.keys()),
                pwd=os.getcwd(),
                branch=branch,
            )
        )

    def _emit(self, event: UIEvent) -> None:
        sink = self.context_factory.event_sink
        if sink is None:
            return
        sink.emit(event)

    def get_user_input(self) -> UserInputResult:
        self._emit(PromptEvent(agent_name=self.current_agent_name.title()))
        user_input = self.input_provider.read().strip()

        if not user_input:
            result = UserInputResult(action="nothing")
            self._emit_action_feedback(result)
            return result

        if user_input.startswith("/agent"):
            user_input_splitted = user_input.split(" ")
            if len(user_input_splitted) > 2:
                raise RuntimeError(
                    f"Command format error. Pick from {get_args(AgentName)} and follow this strict format: `/agent {{agent_name}}`"
                )

            agent_name = user_input_splitted[1].lower()
            if agent_name == self.current_agent_name:
                result = UserInputResult(action="nothing")
                self._emit_action_feedback(result)
                return result

            if agent_name not in get_args(AgentName):
                raise RuntimeError(
                    f"{agent_name} not a valid agent. Pick from {get_args(AgentName)} and follow this strict format: `/agent {{agent_name}}`"
                )
            self.current_agent_name = cast("AgentName", agent_name)
            result = UserInputResult(action="switch_agent", feedback="Agent switched")
            self._emit_action_feedback(result)
            return result

        if user_input in ("/q", "/quit", "exit"):
            result = UserInputResult(action="quit")
            self._emit_action_feedback(result)
            return result

        if user_input in ("/c", "/clear"):
            self.context = self.context_factory.root()
            result = UserInputResult(action="clear", feedback="Cleared conversation")
            self._emit_action_feedback(result)
            return result

        if user_input.startswith("/"):
            result = UserInputResult(action="nothing")
            self._emit_action_feedback(result)
            return result

        self.context.add_user_message(UserMessage(role="user", content=user_input))
        result = UserInputResult(action="conversation")
        self._emit_action_feedback(result)
        return result

    def start_multiturn_loop(self) -> None:
        while True:
            try:
                user_input_result = self.get_user_input()
                if user_input_result.action == "quit":
                    break
                if user_input_result.action != "conversation":
                    continue
                self.get_agent().run(self.context)

            except (KeyboardInterrupt, EOFError):
                self._emit(NewlineEvent())
                self._emit(SeparatorEvent())
                self._emit(TextEvent("Goodbye!"))
                with open("session.json", "w") as fd:
                    json.dump(list(self.context), fd, ensure_ascii=False, indent=2)
                break
            except Exception as err:
                self._emit(TextEvent(str(err), kind="error"))

    def start(self) -> None:
        self._emit_session_info()
        self.start_multiturn_loop()
