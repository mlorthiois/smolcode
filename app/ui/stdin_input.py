from app.backend.protocols import InputProvider


class StdinInputProvider(InputProvider):
    def read(self) -> str:
        return input()
