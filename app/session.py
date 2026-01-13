import json
from dataclasses import dataclass, field
from typing import cast, get_args

from app.agents import AGENTS, Agent, AgentName
from app.schemas import Action, FunctionCall, FunctionCallOutput, Input, Message
from app.ui import (
    RED,
    RESET,
    ui_header,
    ui_input,
    ui_text,
    ui_tool_extract,
    ui_tool_result,
)


@dataclass
class Session:
    agent: AgentName
    messages: list[Input] = field(default_factory=list)

    def get_agent(self) -> Agent:
        return AGENTS[self.agent]

    @ui_input
    def get_user_input(self) -> Action:
        user_input = input().strip()

        if not user_input:
            return "nothing"

        if user_input.startswith("/agent"):
            user_input_splitted = user_input.split(" ")
            if len(user_input_splitted) > 2:
                raise RuntimeError(
                    f"Command format error. Pick from {get_args(AgentName)} and follow this strict format: `/agent {{agent_name}}`"
                )

            agent_name = user_input_splitted[1].lower()
            if agent_name == self.agent:
                return "nothing"

            if agent_name not in get_args(AgentName):
                raise RuntimeError(
                    f"{agent_name} not a valid agent. Pick from {get_args(AgentName)} and follow this strict format: `/agent {{agent_name}}`"
                )
            self.agent = cast("AgentName", agent_name)
            return "switch_agent"

        if user_input in ("/q", "/quit", "exit"):
            exit()

        if user_input in ("/c", "/clear"):
            self.messages = []
            return "clear"

        self.messages.append(Message(role="user", content=user_input))
        return "conversation"

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

    def step(self):
        while True:
            response = self.get_agent().call(self.messages)
            response_output = response["output"]

            for i, block in enumerate(response_output):
                if block["type"] == "message":
                    content = self.extract_text(block)
                    self.messages.append(Message(role="assistant", content=content))

                    # If ends with text, stop the loop
                    if i == len(response_output) - 1:
                        return

                if block["type"] == "function_call":
                    function_call = self.extract_tool(block)
                    function_call_output = self.run_tool(function_call)
                    self.messages += [
                        cast("Input", function_call),
                        cast("Input", function_call_output),
                    ]

                print()

        return

    @ui_header
    def start(self):
        while True:
            try:
                user_action = self.get_user_input()
                if user_action != "conversation":
                    continue
                self.step()
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as err:
                print(f"{RED}⏺ Error: {err}{RESET}")
