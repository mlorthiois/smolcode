from typing import TypedDict

from app.tool import Tool


class Args(TypedDict):
    path: str
    content: str


class WriteTool(Tool[Args]):
    description = "Write content to file"
    args_type = Args

    def __call__(self, args: Args):
        with open(args["path"], "w") as f:
            f.write(args["content"])
        return "Successfull write."
