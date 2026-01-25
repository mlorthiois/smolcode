import sys

from app.backend.context import ContextFactory
from app.backend.registry import Registry
from app.backend.session import Session
from app.plugins.provider import Provider
from app.plugins.provider.auth import AuthContext
from app.ui.null_ui import NullUi
from app.ui.stdin_input import StdinInputProvider
from app.ui.terminal_ui import RED, RESET, TerminalUI


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        try:
            AuthContext.login_oauth()
            return
        except KeyboardInterrupt:
            sys.exit(1)

    try:
        auth = AuthContext.from_environment()
        provider = Provider(auth)

        if sys.stdout.isatty():
            ui = TerminalUI()
            input_provider = StdinInputProvider()
        else:
            ui = NullUi()
            input_provider = StdinInputProvider()

        context_factory = ContextFactory(event_sink=ui)
        registry = Registry(provider, context_factory)
        session = Session(
            current_agent_name="plan",
            registry=registry,
            context_factory=context_factory,
            input_provider=input_provider,
        )
    except Exception as e:
        print(f"{RED}Error initiating session.{RESET}", file=sys.stderr)
        print(f"{RED}{e}{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        session.start()
    except Exception as e:
        print(
            f"{RED}Unexpected error happened during session.\nReason: {e}{RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
