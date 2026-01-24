import json
import os
import re
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import ParamSpec, Protocol, Self, TextIO, TypeVar

from app.schemas import FunctionCall, FunctionCallOutput, UserInputResult

RESET, BOLD, ITALIC, DIM, BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[0m",
    "\033[1m",
    "\033[3m",
    "\033[2m",
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)

HEADER = r"""
>                          | Auth:      {auth}
>                          | Dir:       {pwd}
> ┏━┓┏┳┓┏━┓╻  ┏━╸┏━┓╺┳┓┏━╸ | Branch:    {branch}
> ┗━┓┃┃┃┃ ┃┃  ┃  ┃ ┃ ┃┃┣╸  | Model:     {model} 
> ┗━┛╹ ╹┗━┛┗━╸┗━╸┗━┛╺┻┛┗━╸ | Tools:     {tools} 
>                          | Skills:    {skills}
>                          | Subagents: {subagents}
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
    auth: str
    subagents: tuple[str, ...]
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
    is_success: bool

    @classmethod
    def from_function_call_output_and_success(
        cls, result: FunctionCallOutput | str, is_success: bool
    ) -> Self:
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
        return cls(
            preview=tuple(preview),
            remaining_lines=remaining_lines,
            is_success=is_success,
        )


# -------------------------------------------------------------------------
# Printer Protocol
# -------------------------------------------------------------------------
class Printer(Protocol):
    def print(self, text: str) -> None: ...
    def render_markdown(self, text: str) -> str: ...


# -------------------------------------------------------------------------
# Renderers
# -------------------------------------------------------------------------
class Renderer(ABC):
    """Abstract base class for UI renderers."""

    def __init__(self, printer: Printer) -> None:
        self.printer = printer

    @abstractmethod
    def text(self, event: TextEvent) -> None:
        pass

    @abstractmethod
    def tool_call(self, event: ToolCallEvent) -> None:
        pass

    @abstractmethod
    def tool_result(self, event: ToolResultEvent) -> None:
        pass

    @abstractmethod
    def newline(self) -> None:
        pass


class DefaultRenderer(Renderer):
    """Standard renderer for primary agent output."""

    def text(self, event: TextEvent) -> None:
        self.printer.print(
            f"{CYAN}⏺{RESET} {self.printer.render_markdown(event.text)}\n"
        )

    def tool_call(self, event: ToolCallEvent) -> None:
        self.printer.print(
            f"{GREEN}⏺ {event.name.capitalize()}{RESET}({DIM}{event.arg_preview}{RESET})\n"
        )

    def tool_result(self, event: ToolResultEvent) -> None:
        color = DIM if event.is_success else RED
        for i, line in enumerate(event.preview):
            prefix = "  └─ " if i == 0 else "     "
            self.printer.print(f"{color}{prefix}{line}{RESET}\n")

        if event.remaining_lines > 0:
            self.printer.print(
                f"{color}    ... +{event.remaining_lines} lines{RESET}\n"
            )

    def newline(self) -> None:
        self.printer.print("\n")


class NestedRenderer(Renderer):
    """Tree-style renderer for subagent output."""

    def __init__(self, printer: Printer, depth: int) -> None:
        super().__init__(printer)
        self.depth = depth

    def _tree_prefix(self, is_last: bool = False) -> str:
        indent = "  " + "│   " * (self.depth - 1)
        connector = "└─ " if is_last else "├─ "
        return f"{DIM}{indent}{connector}{RESET}"

    def _tree_continuation(self) -> str:
        return f"{DIM}  " + "│  " * self.depth + f"{RESET}"

    def text(self, event: TextEvent) -> None:
        pass

    def tool_call(self, event: ToolCallEvent) -> None:
        prefix = self._tree_prefix()
        self.printer.print(
            f"{prefix}{GREEN}⏺ {event.name.capitalize()}{RESET}({DIM}{event.arg_preview}{RESET})\n"
        )

    def tool_result(self, event: ToolResultEvent) -> None:
        color = DIM if event.is_success else RED
        cont = self._tree_continuation()
        if event.preview:
            self.printer.print(f"{cont}⎿ {color}{event.preview[0]}{RESET}\n")

    def newline(self) -> None:
        pass


# -------------------------------------------------------------------------
# TUI
# -------------------------------------------------------------------------
class TerminalUI:
    def __init__(self, out: TextIO | None = None) -> None:
        self.out = out if out is not None else sys.stdout
        self._renderer_stack: list[Renderer] = [DefaultRenderer(self)]

    def _current_renderer(self) -> Renderer:
        return self._renderer_stack[-1]

    def push_renderer(self, renderer: Renderer) -> None:
        self._renderer_stack.append(renderer)

    def pop_renderer(self) -> None:
        if len(self._renderer_stack) > 1:
            self._renderer_stack.pop()

    def _terminal_width(self) -> int:
        size = shutil.get_terminal_size(fallback=(100, 20))
        return min(size.columns, 100)

    def _separator(self) -> str:
        return f"{DIM}{'─' * self._terminal_width()}{RESET}"

    def print(self, text: str) -> None:
        self.out.write(text)

    def render_markdown(self, text: str) -> str:
        def apply_inline_styles(line: str) -> str:
            code_spans: list[str] = []

            def stash_code(match: re.Match[str]) -> str:
                code_spans.append(match.group(1))
                return f"\0CODE{len(code_spans) - 1}\0"

            line = re.sub(r"`([^`]+)`", stash_code, line)
            line = re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", line)
            line = re.sub(
                r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
                f"{ITALIC}\\1{RESET}",
                line,
            )
            line = re.sub(
                r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)",
                f"{ITALIC}\\1{RESET}",
                line,
            )

            for index, code in enumerate(code_spans):
                placeholder = f"\0CODE{index}\0"
                line = line.replace(placeholder, f"{YELLOW}{code}{RESET}")

            return line

        rendered_lines: list[str] = []
        for line in text.split("\n"):
            match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if match:
                level = len(match.group(1))
                title_text = apply_inline_styles(match.group(2))
                color = BLUE if level == 1 else CYAN if level == 2 else GREEN
                rendered_lines.append(f"{BOLD}{color}{title_text}{RESET}")
                continue

            rendered_lines.append(apply_inline_styles(line))

        return "\n".join(rendered_lines)

    def error(self, event: TextEvent) -> None:
        self.print(f"{RED}⏺ Error: {event.text}{RESET}\n")

    def newline(self) -> None:
        self._current_renderer().newline()

    def separator_line(self) -> None:
        self.print(self._separator() + "\n")

    def _clear_screen_if_tty(self, out: TextIO) -> None:
        if not out.isatty():
            return
        self.print("\033[2J\033[H")

    def header(self, event: HeaderEvent) -> None:
        self._clear_screen_if_tty(self.out)
        self.separator_line()
        self.separator_line()

        self.print(
            HEADER.format(
                pwd=event.pwd,
                branch=event.branch,
                model=event.model,
                tools=", ".join(event.tools),
                skills=", ".join(event.skills),
                auth=format_auth_mode(event.auth),
                subagents=", ".join(event.subagents),
            )
            + "\n"
        )
        self.separator_line()

    def prompt(self, event: PromptEvent) -> None:
        self.print(self._separator() + "\n")
        self.print(f"{BOLD}{BLUE}({event.agent_name}) ❯{RESET} ")
        self.out.flush()

    def text(self, event: TextEvent) -> None:
        self._current_renderer().text(event)

    def status(self, event: TextEvent) -> None:
        self.print(f"{GREEN}⏺ {self.render_markdown(event.text)}{RESET}\n")

    def tool_call(self, event: ToolCallEvent) -> None:
        self._current_renderer().tool_call(event)

    def tool_result(self, event: ToolResultEvent) -> None:
        self._current_renderer().tool_result(event)


# -------------------------------------------------------------------------
# TUI API
# -------------------------------------------------------------------------
_ui: TerminalUI | None = None


def require_ui() -> TerminalUI:
    if _ui is None:
        raise RuntimeError("UI not initialized (did you call Session.start()?)")
    return _ui


def set_ui(ui: TerminalUI) -> None:
    global _ui
    _ui = ui


def clear_ui() -> None:
    global _ui
    _ui = None


# -------------------------------------------------------------------------
# Depth management (delegates to renderer stack)
# -------------------------------------------------------------------------
_depth: int = 0


def push_depth() -> None:
    global _depth
    _depth += 1
    ui = require_ui()
    ui.push_renderer(NestedRenderer(ui, _depth))


def pop_depth() -> None:
    global _depth
    _depth = max(0, _depth - 1)
    require_ui().pop_renderer()


def get_depth() -> int:
    return _depth


# -------------------------------------------------------------------------
# Decorators
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
    func: Callable[P, tuple[FunctionCallOutput, bool]],
) -> Callable[P, tuple[FunctionCallOutput, bool]]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> tuple[FunctionCallOutput, bool]:
        result, is_success = func(*args, **kwargs)
        require_ui().tool_result(
            ToolResultEvent.from_function_call_output_and_success(result, is_success)
        )
        return result, is_success

    return wrapper


def format_auth_mode(mode: str) -> str:
    if mode == "oauth":
        return "OAuth"
    if mode == "api_key":
        return "API key"
    return mode
