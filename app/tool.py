from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import (
    Any,
    ClassVar,
    NotRequired,
    TypeVar,
    get_args,
    get_origin,
    get_type_hints,
)

from app.utils.schemas import ToolSchema


def _unwrap_not_required(t: object) -> object:
    origin = get_origin(t)
    if origin is NotRequired:
        args = get_args(t)
        if args:
            return args[0]
    return t


def _schema_from_typed_dict(td: type) -> dict[str, object]:
    hints = get_type_hints(td, include_extras=True)
    required = set(getattr(td, "__required_keys__", ()))
    properties: dict[str, dict[str, object]] = {}

    def json_type(t: object) -> str:
        if t is int:
            return "integer"
        if t is float:
            return "number"
        if t is bool:
            return "boolean"
        if t is str:
            return "string"
        return "string"

    for name, t in hints.items():
        base_t = _unwrap_not_required(t)
        jtype = json_type(base_t)
        properties[name] = {"type": jtype}

    return {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
    }


ArgsT = TypeVar("ArgsT", bound=Mapping[str, object])


@dataclass
class Tool[ArgsT = Mapping[str, object]](ABC):
    description: ClassVar[str]
    args_type: ClassVar[type]

    def make_schema(self, name: str) -> ToolSchema:
        return ToolSchema(
            name=name,
            description=self.description,
            parameters=_schema_from_typed_dict(self.args_type),
        )

    @abstractmethod
    def __call__(self, args: ArgsT) -> str:
        raise NotImplementedError


ToolAny = Tool[Any]
