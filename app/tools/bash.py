import subprocess

from app.core.tool import Tool


class BashTool(Tool):
    description = "Run bash command"
    args = {"cmd": "string"}

    def __call__(self, args):
        result = subprocess.run(
            args["cmd"], shell=True, capture_output=True, text=True, timeout=30
        )
        return (result.stdout + result.stderr).strip() or "(No content)"
