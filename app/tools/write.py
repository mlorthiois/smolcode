from app.core.tool import Tool


class WriteTool(Tool):
    description = "Write content to file"
    args = {"path": "string", "content": "string"}

    def __call__(self, args):
        with open(args["path"], "w") as f:
            f.write(args["content"])
        return "Successfull write."
