from app.core.types import (
    AssistantMessage,
    FunctionCall,
    FunctionCallOutput,
    Input,
    Reasoning,
    UserMessage,
)

from .events import (
    DepthEvent,
    TextEvent,
    ToolResultEvent,
    UIEvent,
)
from .protocols import EventSink


class Context(list[Input]):
    def __init__(
        self,
        *,
        event_sink: EventSink | None = None,
        depth_events: bool = False,
    ) -> None:
        super().__init__()
        self._event_sink = event_sink
        self._depth_events = depth_events
        self._depth_active = False

    def __enter__(self) -> "Context":
        if self._depth_events and not self._depth_active:
            self._emit(DepthEvent(delta=1))
            self._depth_active = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._depth_events and self._depth_active:
            self._emit(DepthEvent(delta=-1))
            self._depth_active = False

    def _emit(self, event: UIEvent) -> None:
        if self._event_sink is None:
            return
        self._event_sink.emit(event)

    # Remove id as `store=False` in codex
    def _add(self, input: Input) -> None:
        if "id" in input:
            del input["id"]  # ty: ignore[invalid-argument-type]
        self.append(input)

    def add_user_message(self, message: UserMessage) -> None:
        self._add(message)

    def add_assistant_message(self, message: AssistantMessage) -> None:
        self._add(message)
        text = message["content"][0]["text"]
        self._emit(TextEvent(text, kind="assistant"))

    def add_reasoning(self, reasoning: Reasoning) -> None:
        self._add(reasoning)
        summary = ""
        # Sometimes summary is empty
        if len(reasoning["summary"]) > 0:
            summary = reasoning["summary"][0]["text"]
            self._emit(TextEvent(summary, kind="reasoning"))

    def add_function_call(self, function_call: FunctionCall) -> None:
        self._add(function_call)

    def add_function_call_output(
        self,
        function_call: FunctionCall,
        function_call_output: FunctionCallOutput,
        is_success: bool,
    ) -> None:
        self._add(function_call_output)

        self._emit(
            ToolResultEvent(
                function_name=function_call["name"],
                function_args=function_call["arguments"],
                content=function_call_output["output"],
                is_success=is_success,
            )
        )


class ContextFactory:
    def __init__(self, event_sink: EventSink | None) -> None:
        self._event_sink = event_sink

    @property
    def event_sink(self) -> EventSink | None:
        return self._event_sink

    def root(self) -> Context:
        return Context(event_sink=self._event_sink, depth_events=False)

    def child(self) -> Context:
        return Context(event_sink=self._event_sink, depth_events=True)
