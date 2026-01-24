import re
from pathlib import Path

from app.tool import Tool


class GrepTool(Tool):
    description = "Search files for regex pattern"
    args = {"pat": "string", "path": "string?"}

    def __call__(self, args):
        pattern = re.compile(args["pat"])

        hits = []

        for p in Path(args.get("path", ".")).glob("**"):
            if p.is_dir():
                continue

            try:  # Binary file
                content = p.read_text()
            except Exception:
                continue

            try:
                for line_num, line in enumerate(content.splitlines()):
                    if pattern.search(line):
                        hits.append(f"{str(p)}:{line_num}:{line.rstrip()}")
            except Exception:
                pass

        return "\n".join(hits[:30]) or "(No content)"
