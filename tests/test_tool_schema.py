import unittest
from typing import NotRequired, TypedDict, cast

from app.core.tool import Tool


class Args(TypedDict):
    path: str
    count: int
    timeout: NotRequired[int]
    hint: NotRequired[str]


class TestToolSchema(unittest.TestCase):
    def test_schema_respects_optional_keys(self) -> None:
        schema = Tool.schema_from_typed_dict(Args)
        properties = cast(dict[str, dict[str, object]], schema["properties"])
        required = cast(list[str], schema["required"])

        self.assertEqual(schema["type"], "object")
        self.assertEqual(required, ["count", "path"])
        self.assertEqual(
            properties["path"],
            {"type": "string"},
        )
        self.assertEqual(
            properties["count"],
            {"type": "integer"},
        )
        self.assertEqual(
            properties["timeout"],
            {"type": "integer"},
        )
        self.assertEqual(
            properties["hint"],
            {"type": "string"},
        )


if __name__ == "__main__":
    unittest.main()
