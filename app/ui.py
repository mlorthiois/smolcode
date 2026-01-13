import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import ParamSpec, Self, TextIO, TypeVar

from app.schemas import FunctionCall, FunctionCallOutput, UserInputResult

RESET, BOLD, DIM, BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[0m",
    "\033[1m",
    "\033[2m",
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)

HEADER = r"""
>                          | Dir:    {pwd}
> ┏━┓┏┳┓┏━┓╻  ┏━╸┏━┓╺┳┓┏━╸ | Branch: {branch}
> ┗━┓┃┃┃┃ ┃┃  ┃  ┃ ┃ ┃┃┣╸  | Model:  {model} 
> ┗━┛╹ ╹┗━┛┗━╸┗━╸┗━┛╺┻┛┗━╸ | Tools:  {tools} 
>                          | Skills: {skills}
""".strip()

P = ParamSpec("P")
R = TypeVar("R")


# -------------------------------------------------------------------------
# Events
# -------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class HeaderEvent:
    model: str
    skills: tuple[str, ...]
    tools: tuple[str, ...]
    pwd: str = os.getcwd()
    branch: str = subprocess.run(
        ["git", "branch", "--show-current"], capture_output=True, text=True
    ).stdout.strip()


@dataclass(frozen=True, slots=True)
class PromptEvent:
    agent_name: str


@dataclass(frozen=True, slots=True)
class TextEvent:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    name: str
    arg_preview: str

    @classmethod
    def from_function_call(cls, call: FunctionCall) -> Self:
        try:
            parsed = json.loads(call.arguments)
        except json.JSONDecodeError:
            return cls(name=call.name, arg_preview="(invalid json)")

        arg_preview = ""
        if isinstance(parsed, dict) and parsed:
            first_value = next(iter(parsed.values()))
            arg_preview = str(first_value)
            if len(arg_preview) > 70:
                arg_preview = arg_preview[:70]

        return cls(name=call.name, arg_preview=arg_preview)


@dataclass(frozen=True, slots=True)
class ToolResultEvent:
    preview: tuple[str, ...]
    remaining_lines: int

    @classmethod
    def from_function_call_output(cls, result: FunctionCallOutput | str) -> Self:
        result_str = result.output if isinstance(result, FunctionCallOutput) else result

        result_lines = result_str.split("\n")
        preview: list[str] = []
        for line in result_lines[:3]:
            if len(line) > 80:
                line = line[:77] + "..."
            if len(line) == 0:
                line = "(No content)"
            preview.append(line)

        remaining_lines = max(len(result_lines) - 3, 0)
        return cls(preview=tuple(preview), remaining_lines=remaining_lines)


# -------------------------------------------------------------------------
# TUI
# -------------------------------------------------------------------------
class TerminalUI:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out = out if out is not None else sys.stdout

    def _terminal_width(self, out: TextIO) -> int:
        size = shutil.get_terminal_size(fallback=(100, 20))
        return min(size.columns, 100)

    def _separator(self, out: TextIO) -> str:
        return f"{DIM}{'─' * self._terminal_width(out)}{RESET}"

    def print(self, text: str) -> None:
        self._out.write(text)

    def error(self, event: TextEvent) -> None:
        self.print(f"{RED}⏺ Error: {event.text}{RESET}\n")

    def newline(self) -> None:
        self.print("\n")

    def separator_line(self) -> None:
        self.print(self._separator(self._out) + "\n")

    def _clear_screen_if_tty(self, out: TextIO) -> None:
        if not out.isatty():
            return
        # ANSI clear screen + cursor home
        self.print("\033[2J\033[H")

    def render_markdown(self, text: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)

    def header(self, event: HeaderEvent) -> None:
        self._clear_screen_if_tty(self._out)
        self.separator_line()
        self.separator_line()

        self.print(
            HEADER.format(
                pwd=event.pwd,
                branch=event.branch,
                model=event.model,
                tools=", ".join(event.tools),
                skills=", ".join(event.skills),
            )
            + "\n"
        )
        self.separator_line()

    def prompt(self, event: PromptEvent) -> None:
        self.print(self._separator(self._out) + "\n")
        self.print(f"{BOLD}{BLUE}({event.agent_name}) ❯{RESET} ")
        self._out.flush()

    def text(self, event: TextEvent) -> None:
        self.print(f"{CYAN}⏺{RESET} {self.render_markdown(event.text)}\n")

    def status(self, event: TextEvent) -> None:
        self.print(f"{GREEN}⏺ {self.render_markdown(event.text)}{RESET}\n")

    def tool_call(self, event: ToolCallEvent) -> None:
        self.print(
            f"{GREEN}⏺ {event.name.capitalize()}{RESET}({DIM}{event.arg_preview}{RESET})\n"
        )

    def tool_result(self, event: ToolResultEvent) -> None:
        for i, line in enumerate(event.preview):
            prefix = "  ⎿ " if i == 0 else "    "
            self.print(f"{DIM}{prefix}{line}{RESET}\n")

        if event.remaining_lines > 0:
            self.print(f"{DIM}    ... +{event.remaining_lines} lines{RESET}\n")


# -------------------------------------------------------------------------
# TUI API
# -------------------------------------------------------------------------
_UI: TerminalUI | None = None


def require_ui() -> TerminalUI:
    if _UI is None:
        raise RuntimeError("UI not initialized (did you call Session.start()?)")
    return _UI


def set_ui(ui: TerminalUI) -> None:
    global _UI
    _UI = ui


def clear_ui() -> None:
    global _UI
    _UI = None


# -------------------------------------------------------------------------
# Expose TUI API to session
# -------------------------------------------------------------------------
def ui_header(
    event_factory: Callable[P, HeaderEvent],
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            require_ui().header(event_factory(*args, **kwargs))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def ui_prompt(
    event_factory: Callable[P, PromptEvent],
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            require_ui().prompt(event_factory(*args, **kwargs))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def ui_user_input(func: Callable[P, UserInputResult]) -> Callable[P, UserInputResult]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> UserInputResult:
        result = func(*args, **kwargs)

        if result.action != "nothing":
            ui = require_ui()
            ui.separator_line()

        if result.feedback is not None:
            ui = require_ui()
            if result.action in ("clear", "switch_agent"):
                ui.status(TextEvent(result.feedback))
            else:
                ui.text(TextEvent(result.feedback))

        return result

    return wrapper


def ui_text(func: Callable[P, str]) -> Callable[P, str]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        text = func(*args, **kwargs)
        require_ui().text(TextEvent(text))
        return text

    return wrapper


def ui_tool_extract(func: Callable[P, FunctionCall]) -> Callable[P, FunctionCall]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> FunctionCall:
        tool = func(*args, **kwargs)
        require_ui().tool_call(ToolCallEvent.from_function_call(tool))
        return tool

    return wrapper


def ui_tool_result(
    func: Callable[P, FunctionCallOutput | str],
) -> Callable[P, FunctionCallOutput | str]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> FunctionCallOutput | str:
        result = func(*args, **kwargs)
        require_ui().tool_result(ToolResultEvent.from_function_call_output(result))
        return result

    return wrapper
