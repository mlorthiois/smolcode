from typing import Protocol

from .agent import Agent


class SessionProtocol(Protocol):
    def get_agent(self) -> Agent: ...

    def start_multiturn_loop(self) -> None:
        """
        while True:
            user_input = get_user_input()  # Handle /quit, /clear, etc.
            if user_input.is_command:
                run_command(user_input.command)
                continue

            self.agent.run(self.messages)  # Delegate to the Agent
        """
        ...
