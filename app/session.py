import json
import sys
from dataclasses import dataclass, field
from typing import cast, get_args

from app.agents import AGENTS, Agent, AgentName
from app.schemas import (
    FunctionCall,
    FunctionCallOutput,
    Input,
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
    ui_text,
    ui_tool_extract,
    ui_tool_result,
    ui_user_input,
)


@dataclass
class Session:
    agent: AgentName
    messages: list[Input] = field(default_factory=list)

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
            self.messages = []
            return UserInputResult(action="clear", feedback="Cleared conversation")

        if user_input.startswith("/"):
            return UserInputResult(action="nothing")

        self.messages.append(Message(role="user", content=user_input))
        return UserInputResult(action="conversation")

    @ui_text
    def extract_text(self, block) -> str:
        return block["content"][0]["text"]

    @ui_tool_extract
    def extract_tool(self, block) -> FunctionCall:
        function_call = FunctionCall(
            call_id=block["call_id"],
            name=block["name"],
            arguments=block.get("arguments", "{}"),
        )
        return function_call

    @ui_tool_result
    def run_tool(self, function_call: FunctionCall) -> FunctionCallOutput | str:
        args = json.loads(function_call.arguments)
        try:
            tool_output = self.get_agent().tools[function_call.name](args)
            return FunctionCallOutput(call_id=function_call.call_id, output=tool_output)
        except Exception as err:
            return f"error: {err}"

    def step(self) -> None:
        while True:
            response = self.get_agent().call(self.messages)
            response_output = response["output"]
            has_tool = False

            for i, block in enumerate(response_output):
                if block["type"] == "message":
                    content = self.extract_text(block)
                    self.messages.append(Message(role="assistant", content=content))

                if block["type"] == "function_call":
                    has_tool = True
                    function_call = self.extract_tool(block)
                    function_call_output = self.run_tool(function_call)
                    self.messages += [
                        cast("Input", function_call),
                        cast("Input", function_call_output),
                    ]

                require_ui().newline()

            # if no tool output to send back to the model, break the model loop
            if not has_tool:
                return

    def start(self) -> None:
        ui = TerminalUI()
        if not ui._out.isatty():
            raise RuntimeError("TTY required")

        set_ui(ui)
        try:
            self._start_loop()
        finally:
            clear_ui()

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
    def _start_loop(self) -> None:
        while True:
            try:
                user_input_result = self.get_user_input()
                if user_input_result.action != "conversation":
                    continue
                self.step()
            except (KeyboardInterrupt, EOFError):
                require_ui().newline()
                require_ui().separator_line()
                require_ui().text(TextEvent("Goodbye!"))
                break
            except Exception as err:
                require_ui().error(TextEvent(str(err)))
