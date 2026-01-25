from collections.abc import Callable
from typing import Protocol

from .events import UIEvent


class EventSink(Protocol):
    def emit(self, event: UIEvent) -> None: ...


class InputProvider(Protocol):
    def read(self) -> str: ...


class EventBus(EventSink):
    def __init__(self) -> None:
        self._subs: list[Callable[[UIEvent], None]] = []

    def subscribe(self, fn: Callable[[UIEvent], None]) -> None:
        self._subs.append(fn)

    def emit(self, event: UIEvent) -> None:
        for fn in self._subs:
            fn(event)
