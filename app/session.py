import sys
from dataclasses import dataclass, field
from typing import cast, get_args

from app.agents import AGENTS, Agent, AgentName
from app.context import Context
from app.schemas import (
    Message,
    UserInputResult,
)
from app.ui import (
    HeaderEvent,
    PromptEvent,
    TerminalUI,
    TextEvent,
    clear_ui,
    require_ui,
    set_ui,
    ui_header,
    ui_prompt,
    ui_user_input,
)


@dataclass
class Session:
    agent: AgentName
    context: Context = field(default_factory=Context)

    def get_agent(self) -> Agent:
        return AGENTS[self.agent]

    @ui_user_input
    @ui_prompt(lambda self: PromptEvent(agent_name=self.agent.title()))
    def get_user_input(self) -> UserInputResult:
        user_input = input().strip()

        if not user_input:
            return UserInputResult(action="nothing")

        if user_input.startswith("/agent"):
            user_input_splitted = user_input.split(" ")
            if len(user_input_splitted) > 2:
                raise RuntimeError(
                    f"Command format error. Pick from {get_args(AgentName)} and follow this strict format: `/agent {{agent_name}}`"
                )

            agent_name = user_input_splitted[1].lower()
            if agent_name == self.agent:
                return UserInputResult(action="nothing")

            if agent_name not in get_args(AgentName):
                raise RuntimeError(
                    f"{agent_name} not a valid agent. Pick from {get_args(AgentName)} and follow this strict format: `/agent {{agent_name}}`"
                )
            self.agent = cast("AgentName", agent_name)
            return UserInputResult(action="switch_agent", feedback="Agent switched")

        if user_input in ("/q", "/quit", "exit"):
            sys.exit()

        if user_input in ("/c", "/clear"):
            self.context = Context()
            return UserInputResult(action="clear", feedback="Cleared conversation")

        if user_input.startswith("/"):
            return UserInputResult(action="nothing")

        self.context.add_user_message(Message(role="user", content=user_input))
        return UserInputResult(action="conversation")

    @ui_header(
        lambda self: HeaderEvent(
            model=self.get_agent().model,
            skills=tuple(
                self.get_agent()
                .tools["skills"]
                .make_schema("skills")
                .parameters["properties"]["skill_name"]["enum"]
            ),
            tools=tuple(tool.name for tool in self.get_agent().tools_schema),
        )
    )
    def start_multiturn_loop(self) -> None:
        while True:
            try:
                user_input_result = self.get_user_input()
                if user_input_result.action != "conversation":
                    continue
                self.get_agent().run(self.context)

            except (KeyboardInterrupt, EOFError):
                require_ui().newline()
                require_ui().separator_line()
                require_ui().text(TextEvent("Goodbye!"))
                break
            except Exception as err:
                require_ui().error(TextEvent(str(err)))

    def start(self) -> None:
        ui = TerminalUI()
        if not ui._out.isatty():
            raise RuntimeError("TTY required")

        set_ui(ui)
        try:
            self.start_multiturn_loop()
        finally:
            clear_ui()
