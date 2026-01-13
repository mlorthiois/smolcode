from app.session import Session


def main():
    session = Session(agent="plan")
    session.start()


if __name__ == "__main__":
    main()
