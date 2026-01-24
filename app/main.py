import sys

from app.provider import Provider
from app.provider.auth import AuthContext, OAuthNotLoggedInError
from app.session import Session
from app.ui import RED, RESET


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        AuthContext.login_oauth()
        return

    try:
        auth = AuthContext.from_environment()
    except OAuthNotLoggedInError as e:
        print(f"{RED}{e}{RESET}", file=sys.stderr)
        sys.exit(1)

    provider = Provider(auth)
    session = Session(agent="plan", provider=provider)
    session.start()


if __name__ == "__main__":
    main()
