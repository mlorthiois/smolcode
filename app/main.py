from app.agents import agent
from app.session import Session


def main():
    session = Session(agent=agent)
    session.start()


if __name__ == "__main__":
    main()
