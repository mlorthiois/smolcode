import subprocess
from typing import TypedDict

from app.core import Tool


class Args(TypedDict):
    cmd: str


class BashTool(Tool[Args]):
    description = "Run bash command"
    args_type = Args

    def __call__(self, args: Args):
        result = subprocess.run(
            args["cmd"], shell=True, capture_output=True, text=True, timeout=30
        )
        return (result.stdout + result.stderr).strip() or "(No content)"
