from typing import Any
import json
from dataclasses import dataclass, field

from app.agents import Agent
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
    messages: list = field(default_factory=list)

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

        self.messages.append({"role": "user", "content": user_input})

    @ui_text
    def extract_text(self, block) -> str:
        return block["content"][0]["text"]

    @ui_tool_extract
    def extract_tool(self, block) -> tuple[str, dict[str, Any]]:
        tool_name = block["name"]
        tool_args = json.loads(block.get("arguments", "{}"))
        return tool_name, tool_args

    @ui_tool_result
    def run_tool(self, name, args) -> str:
        try:
            tool_output = self.agent.tools[name](args)
            return tool_output
        except Exception as err:
            return f"error: {err}"

    def step(self):
        while True:
            response = self.agent.call(self.messages)
            response_output = response["output"]
            self.messages += response_output

            for block in response_output:
                if block["type"] == "message":
                    self.extract_text(block)
                    return

                if block["type"] == "function_call":
                    tool_name, tool_args = self.extract_tool(block)
                    result = self.run_tool(tool_name, tool_args)

                    self.messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": block["call_id"],
                            "output": result,
                        }
                    )

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
