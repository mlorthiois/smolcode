import json
import os
import urllib.request
from dataclasses import asdict
from typing import Any

from app.schemas import Input, ToolSchema

API_URL = "https://api.openai.com/v1/responses"
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]


def call_api(
    messages: list[Input],
    model: str,
    system_prompt: str,
    tools_schema: list[ToolSchema],
) -> dict[str, Any]:
    # Serialize inputs
    input = [asdict(m) for m in messages]
    tools_schema_json = [asdict(schema) for schema in tools_schema]

    payload = json.dumps(
        {
            "model": model,
            "max_output_tokens": 8192,
            "instructions": system_prompt,
            "input": input,
            "tools": tools_schema_json,
        }
    ).encode()

    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
    )

    response = urllib.request.urlopen(request)
    return json.loads(response.read())
