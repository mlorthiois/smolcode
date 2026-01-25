import json
import re
import shutil
import sys
from abc import ABC, abstractmethod
from typing import Protocol, TextIO

from app.backend.events import (
    DepthEvent,
    NewlineEvent,
    PromptEvent,
    SeparatorEvent,
    SessionInfoEvent,
    TextEvent,
    ToolResultEvent,
    UIEvent,
)
from app.backend.protocols import EventSink

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


def apply_base_style(text: str, style: str) -> str:
    if not style:
        return text
    return f"{style}{text.replace(RESET, RESET + style)}{RESET}"


HEADER = r"""
>                          | Auth:      {auth}
>                          | Dir:       {pwd}
> ┏━┓┏┳┓┏━┓╻  ┏━╸┏━┓╺┳┓┏━╸ | Branch:    {branch}
> ┗━┓┃┃┃┃ ┃┃  ┃  ┃ ┃ ┃┃┣╸  | Model:     {model} 
> ┗━┛╹ ╹┗━┛┗━╸┗━╸┗━┛╺┻┛┗━╸ | Tools:     {tools} 
>                          | Skills:    {skills}
>                          | Subagents: {subagents}
""".strip()


def format_auth_mode(mode: str) -> str:
    if mode == "oauth":
        return "OAuth"
    if mode == "api_key":
        return "API"
    return mode


def parse_function_call_args(event: ToolResultEvent) -> str:
    try:
        parsed = json.loads(event.function_args)
    except json.JSONDecodeError:
        return "<...>"

    arg_preview = ", ".join([f"{key}={value}" for key, value in parsed.items()])
    if len(arg_preview) > 70:
        return arg_preview[:70] + "..."
    return arg_preview


def parse_function_call_output_event(event: ToolResultEvent) -> tuple[list[str], int]:
    result_lines = event.content.split("\n")
    preview: list[str] = []
    for line in result_lines[:3]:
        if len(line) > 80:
            line = line[:77] + "..."
        if len(line) == 0:
            line = ""
        preview.append(line)

    remaining_lines = max(len(result_lines) - 3, 0)
    return preview, remaining_lines


class Printer(Protocol):
    def print(self, text: str) -> None: ...
    def render_markdown(self, text: str) -> str: ...


class Renderer(ABC):
    """Abstract base class for UI renderers."""

    def __init__(self, printer: Printer) -> None:
        self.printer = printer

    @abstractmethod
    def text(self, event: TextEvent) -> None:
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
        if len(event.text) == 0:
            return
        if event.kind == "reasoning":
            rendered = apply_base_style(self.printer.render_markdown(event.text), DIM)
            self.printer.print(f"{DIM}⏺{RESET} {rendered}\n")
            return

        self.printer.print(
            f"{BLUE}⏺{RESET} {self.printer.render_markdown(event.text)}\n"
        )

    def tool_result(self, event: ToolResultEvent) -> None:
        color = DIM if event.is_success else RED
        args_preview = parse_function_call_args(event)
        preview, remaining_lines = parse_function_call_output_event(event)

        self.printer.print(
            f"{GREEN}⏺ {event.function_name.capitalize()}{RESET}({DIM}{args_preview}{RESET})\n"
        )

        for i, line in enumerate(preview):
            prefix = "  └─ " if i == 0 else "     "
            self.printer.print(f"{color}{prefix}{line}{RESET}\n")

        if remaining_lines > 0:
            self.printer.print(f"{color}    ... +{remaining_lines} lines{RESET}\n")

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

    def tool_result(self, event: ToolResultEvent) -> None:
        color = DIM if event.is_success else RED
        args_preview = parse_function_call_args(event)
        preview, _ = parse_function_call_output_event(event)
        prefix = self._tree_prefix()
        self.printer.print(
            f"{prefix}{GREEN}⏺ {event.function_name.capitalize()}{RESET}({DIM}{args_preview}{RESET})\n"
        )

        cont = self._tree_continuation()
        if event.content:
            self.printer.print(f"{cont}⎿ {color}{preview[0]}{RESET}\n")

    def newline(self) -> None:
        pass


class TerminalUI(EventSink):
    def __init__(self, out: TextIO | None = None) -> None:
        self.out = out if out is not None else sys.stdout
        self._renderer_stack: list[Renderer] = [DefaultRenderer(self)]
        self._depth = 0

    def emit(self, event: UIEvent) -> None:
        if isinstance(event, SessionInfoEvent):
            self.header(event)
            return

        if isinstance(event, PromptEvent):
            self.prompt(event)
            return

        if isinstance(event, TextEvent):
            if event.kind == "status":
                self.status(event)
                return
            if event.kind == "error":
                self.error(event)
                return
            self.text(event)
            return

        if isinstance(event, ToolResultEvent):
            self.tool_result(event)
            return

        if isinstance(event, NewlineEvent):
            self.newline()
            return

        if isinstance(event, SeparatorEvent):
            self.separator_line()
            return

        if isinstance(event, DepthEvent):
            self._adjust_depth(event.delta)
            return

    def _current_renderer(self) -> Renderer:
        return self._renderer_stack[-1]

    def _adjust_depth(self, delta: int) -> None:
        if delta > 0:
            for _ in range(delta):
                self._depth += 1
                self.push_renderer(NestedRenderer(self, self._depth))
        elif delta < 0:
            for _ in range(-delta):
                if self._depth == 0:
                    break
                self._depth -= 1
                self.pop_renderer()

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

    @staticmethod
    def render_markdown(text: str) -> str:
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

    def header(self, event: SessionInfoEvent) -> None:
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

    def tool_result(self, event: ToolResultEvent) -> None:
        self._current_renderer().tool_result(event)
