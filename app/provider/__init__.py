import json
import urllib.request
from dataclasses import asdict
from typing import Any
from urllib import error as urllib_error

from app.context import Context
from app.utils.schemas import ToolSchema

from .auth import AuthContext


class Provider:
    def __init__(self, auth: AuthContext) -> None:
        self.auth = auth

    def call(
        self,
        context: Context,
        model: str,
        system_prompt: str,
        tools_schema: list[ToolSchema],
    ) -> dict[str, Any]:
        body = self._build_request_body(
            context=context,
            model=model,
            system_prompt=system_prompt,
            tools_schema=tools_schema,
        )
        headers = self.auth.request_headers()
        payload = json.dumps(body).encode()

        request = urllib.request.Request(
            self.auth.get_base_url(),
            data=payload,
            headers=headers,
        )

        try:
            response = urllib.request.urlopen(request)
            raw = response.read().decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            if (
                "text/event-stream" in content_type
                or raw.lstrip().startswith("data:")
                or raw.lstrip().startswith("event:")
                or "\ndata:" in raw
            ):
                return self._parse_streaming_response(raw)
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                message = raw.strip()
                if not message:
                    raise RuntimeError("Provider response was empty.") from exc
                raise RuntimeError(
                    f"Provider response was not JSON: {message}"
                ) from exc
        except urllib_error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            message = raw or exc.reason
            raise RuntimeError(
                f"Provider request failed (status={exc.code}): {message}"
            ) from exc

    def _build_request_body(
        self,
        *,
        context: Context,
        model: str,
        system_prompt: str,
        tools_schema: list[ToolSchema],
    ) -> dict[str, Any]:
        provider_input = context.to_provider_input()
        tools_schema_json = [asdict(schema) for schema in tools_schema]

        body: dict[str, Any] = {
            "model": model,
            "instructions": system_prompt,
            "input": provider_input,
            "tools": tools_schema_json,
            "store": False,
            "stream": True,
        }
        return body

    @staticmethod
    def _parse_streaming_response(raw: str) -> dict[str, Any]:
        last_response: dict[str, Any] | None = None
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and isinstance(data.get("response"), dict):
                last_response = data["response"]
        if last_response is None:
            raise RuntimeError("Streaming response missing final payload.")
        return last_response
