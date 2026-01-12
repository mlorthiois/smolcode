from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from app.schemas import ToolSchema


@dataclass
class Tool(ABC):
    description: ClassVar[str]
    args: ClassVar[dict[str, str]]

    def make_schema(self, name: str) -> ToolSchema:
        properties = {}
        required = []
        for param_name, param_type in self.args.items():
            is_optional = param_type.endswith("?")
            base_type = param_type.rstrip("?")
            properties[param_name] = {
                "type": "integer" if base_type == "number" else base_type
            }
            if not is_optional:
                required.append(param_name)

        return ToolSchema(
            name=name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
        )

    @abstractmethod
    def __call__(self, *args, **kwargs) -> str:
        raise NotImplementedError
