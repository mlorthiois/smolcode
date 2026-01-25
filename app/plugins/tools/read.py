from typing import NotRequired, TypedDict

from app.core import Tool


class Args(TypedDict):
    path: str
    offset: NotRequired[int]
    limit: NotRequired[int]


class ReadTool(Tool[Args]):
    description = "Read file with line numbers (file path, not directory)"
    args_type = Args

    def __call__(self, args: Args):
        with open(args["path"]) as fd:
            lines = fd.readlines()

        offset = args.get("offset", 0)
        limit = args.get("limit", len(lines))
        selected = lines[offset : offset + limit]

        return "".join(
            f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected)
        )
