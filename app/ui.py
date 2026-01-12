import os
import re

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

HEADER = r"""                     _               _      
 ___ _ __ ___   ___ | | ___ ___   __| | ___ 
/ __| '_ ` _ \ / _ \| |/ __/ _ \ / _` |/ _ \
\__ \ | | | | | (_) | | (_| (_) | (_| |  __/
|___/_| |_| |_|\___/|_|\___\___/ \__,_|\___|
"""


def separator() -> str:
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 100)}{RESET}"


def render_markdown(text) -> str:
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def ui_header(func):
    def myinner(*args, **kwargs):
        agent = args[0].agent
        os.system("clear||cls")  # Clear the terminal to be in "fullscreen"
        print(separator())
        print(HEADER)
        print(separator())
        skills_schema = agent.tools["skills"].make_schema("skills")
        skills = skills_schema["parameters"]["properties"]["skill_name"]["enum"]
        print(f"Model: {agent.model}")
        print(f"Skills loaded: {len(skills)} ({', '.join(list(skills))})")
        print(
            f"Tools loaded: {len(agent.tools_schema)} ({', '.join([tool['name'] for tool in agent.tools_schema])})"
        )
        _ = func(*args, **kwargs)

    return myinner


def ui_input(func):
    def myinner(*args, **kwargs):
        print(separator())
        print(f"{BOLD}{BLUE}❯{RESET} ", end="")

        user_input = func(*args, **kwargs)
        if user_input == "/c":
            print(f"{GREEN}⏺ Cleared conversation{RESET}")

        print(separator())
        return user_input

    return myinner


def ui_text(func):
    def myinner(*args, **kwargs):
        text = func(*args, **kwargs)
        print(f"\n{CYAN}⏺{RESET} {render_markdown(text)}")
        return text

    return myinner


def ui_tool_extract(func):
    def myinner(*args, **kwargs):
        tool_name, tool_args = func(*args, **kwargs)
        if len(tool_args) == 0:
            arg_preview = ""
        else:
            arg_preview = str(list(tool_args.values())[0])
            if len(arg_preview) > 70:
                arg_preview = arg_preview[:70]
        print(f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})")
        return tool_name, tool_args

    return myinner


def ui_tool_result(func):
    def myinner(*args, **kwargs):
        result = func(*args, **kwargs)

        result_lines = result.split("\n")
        for i, line in enumerate(result_lines):
            if i > 2:
                break

            if len(line) > 80:
                line = line[:77] + "..."

            if len(line) == 0:
                line = "(No content)"

            if i == 0:
                prefix = "  ⎿ "
            else:
                prefix = "    "

            print(f"{DIM}{prefix}{line}{RESET}")

        if len(result_lines) > 3:
            print(f"{DIM}    ... +{max(len(result_lines) - 3, 0)} lines{RESET}")

        return result

    return myinner
