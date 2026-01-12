import json
from dataclasses import dataclass, field
from typing import cast

from app.agents import Agent
from app.schemas import FunctionCall, FunctionCallOutput, Input, Message
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
    agent: Agent
    messages: list[Input] = field(default_factory=list)

    @ui_input
    def get_user_input(self):
        user_input = input().strip()

        if not user_input:
            return

        if user_input in ("/q", "/quit", "exit"):
            exit()

        if user_input in ("/c", "/clear"):
            self.messages = []
            return

        self.messages.append(Message(role="user", content=user_input))

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
            tool_output = self.agent.tools[function_call.name](args)
            return FunctionCallOutput(call_id=function_call.call_id, output=tool_output)
        except Exception as err:
            return f"error: {err}"

    def step(self):
        while True:
            response = self.agent.call(self.messages)
            response_output = response["output"]

            for block in response_output:
                if block["type"] == "message":
                    content = self.extract_text(block)
                    self.messages.append(Message(role="assistant", content=content))
                    return

                if block["type"] == "function_call":
                    function_call = self.extract_tool(block)
                    function_call_output = self.run_tool(function_call)
                    self.messages += [
                        cast("Input", function_call),
                        cast("Input", function_call_output),
                    ]

        return

    @ui_header
    def start(self):
        while True:
            try:
                self.get_user_input()
                self.step()
                print()
            except (KeyboardInterrupt, EOFError):
                break
            except Exception as err:
                print(f"{RED}⏺ Error: {err}{RESET}")
