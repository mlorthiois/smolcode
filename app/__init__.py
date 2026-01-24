import sys

from app.provider import Provider
from app.provider.auth import AuthContext
from app.session import Session
from app.utils.registry import Registry
from app.utils.ui import RED, RESET


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
        registry = Registry(provider)
    except Exception as e:
        print(f"{RED}Error initiating session.{RESET}", file=sys.stderr)
        print(f"{RED}{e}{RESET}", file=sys.stderr)
        sys.exit(1)

    session = Session(current_agent_name="plan", registry=registry)
    session.start()


if __name__ == "__main__":
    main()
