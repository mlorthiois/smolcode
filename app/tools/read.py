from app.core.tool import Tool


class ReadTool(Tool):
    description = "Read file with line numbers (file path, not directory)"
    args = {"path": "string", "offset": "number?", "limit": "number?"}

    def __call__(self, args):
        with open(args["path"]) as fd:
            lines = fd.readlines()

        offset = args.get("offset", 0)
        limit = args.get("limit", len(lines))
        selected = lines[offset : offset + limit]

        return "".join(
            f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected)
        )
