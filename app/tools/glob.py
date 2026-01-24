from pathlib import Path
from typing import NotRequired, TypedDict

from app.tool import Tool


class Args(TypedDict):
    pat: str
    path: NotRequired[str]


class GlobTool(Tool[Args]):
    description = "Find files by pattern, sorted by mtime"
    args_type = Args

    def __call__(self, args: Args) -> str:
        files = list(Path(args.get("path", ".")).glob(args["pat"]))

        if len(files) == 0:
            return "(No content)"

        files = sorted(
            files,
            key=lambda p: p.stat().st_mtime if p.is_file() else 0,
            reverse=True,
        )

        return "\n".join([str(p) for p in files])
