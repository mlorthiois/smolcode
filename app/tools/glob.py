from pathlib import Path

from app.tool import Tool


class GlobTool(Tool):
    description = "Find files by pattern, sorted by mtime"
    args = {"pat": "string", "path": "string?"}

    def __call__(self, args) -> str:
        files = list(Path(args.get("path", ".")).glob(args["pat"]))

        if len(files) == 0:
            return "(No content)"

        files = sorted(
            files,
            key=lambda p: p.stat().st_mtime if p.is_file() else 0,
            reverse=True,
        )

        return "\n".join([str(p) for p in files])
