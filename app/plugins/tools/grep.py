import re
from pathlib import Path
from typing import NotRequired, TypedDict

from app.core import Tool


class Args(TypedDict):
    pat: str
    path: NotRequired[str]


class GrepTool(Tool[Args]):
    description = "Search files for regex pattern"
    args_type = Args

    def __call__(self, args: Args):
        pattern = re.compile(args["pat"])

        hits: list[str] = []

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
