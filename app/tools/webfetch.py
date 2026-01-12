import urllib.request

from .base_tool import Tool

MAX_BYTES: int = 1_000_000
TIMEOUT_SEC: float = 10.0

description = """\
- Fetches content from a specified URL. Use this tool when you need to retrieve and analyze web content.
- The content will not be converted, try to use raw URLs if possible (raw.githubusercontent.com instead of github.com for example).
- The URL must be a fully-formed valid URL.
"""


class WebFetchTool(Tool):
    description = description
    args = {"url": "string"}

    def __call__(self, args):
        url = args["url"]
        req = urllib.request.Request(url, method="GET")

        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            raw = resp.read(MAX_BYTES + 1)
            resp_headers = dict(resp.headers.items())
            status = resp.status

        if len(raw) > MAX_BYTES:
            raise ValueError(f"Response too large (> {MAX_BYTES} bytes)")

        charset = "utf-8"
        ct = resp_headers.get("Content-Type", "")
        if "charset=" in ct.lower():
            charset = ct.split("charset=")[-1].split(";")[0].strip()

        content = raw.decode(charset, errors="replace")

        if status >= 400:
            raise Exception(
                f"Cannot access {url}. Status code: {status}. Content: {content}"
            )

        return content
