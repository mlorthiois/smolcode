from typing import Any, Literal, Protocol

from .context import ContextProtocol
from .tool import ToolSchema

AuthMode = Literal["oauth", "api_key"]


class ProviderProtocol(Protocol):
    def auth_mode(self) -> AuthMode: ...

    def call(
        self,
        context: ContextProtocol,
        model: str,
        instructions: str,
        tools_schema: list[ToolSchema],
    ) -> dict[str, Any]:
        """
        payload = json.dumps({
            "model": model,
            "instructions": system_prompt,
            "conversation": context,
            "tools": tools_schema
        }).encode()

        response = Request(
            API_URL,
            data=payload,
        ).send().read()

        return json.loads(response))
        """
        ...
