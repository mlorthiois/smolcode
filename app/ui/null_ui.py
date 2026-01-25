from app.backend.events import UIEvent
from app.backend.protocols import EventSink


class NullUi(EventSink):
    """
    Used for non-TTY sessions.
    """

    def emit(self, event: UIEvent) -> None:
        pass
