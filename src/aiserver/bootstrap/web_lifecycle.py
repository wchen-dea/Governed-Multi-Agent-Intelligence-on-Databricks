"""Web-process lifecycle management."""

from aiserver.bootstrap.container import AppDependencyContainer


class WebProcessLifecycle:
    """Own shutdown behavior that belongs to the stateless web process."""

    def __init__(self, container: AppDependencyContainer) -> None:
        self._container = container

    async def start(self) -> None:
        """Start web-only lifecycle collaborators."""

    async def stop(self) -> None:
        """Stop web-only lifecycle collaborators."""

    def close(self) -> None:
        """Flush a closeable lifecycle-event adapter."""
        close = getattr(self._container.message_bus, "close", None)
        if callable(close):
            close()
