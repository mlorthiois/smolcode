from typing import Any
import json
import os
import urllib.request

API_URL = "https://api.openai.com/v1/responses"
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]


def call_api(messages, model, system_prompt, tools) -> dict[str, Any]:
    payload = json.dumps(
        {
            "model": model,
            "max_output_tokens": 8192,
            "instructions": system_prompt,
            "input": messages,
            "tools": tools,
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
