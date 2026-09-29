"""Application port for shared conversation route affinity."""

from typing import Protocol

from aiserver.contracts.execution import RouteAffinity


class RouteAffinityStore(Protocol):
    """Persist route affinity without coupling routing to a storage backend."""

    def get(self, conversation_id: str) -> RouteAffinity | None: ...

    def put(self, affinity: RouteAffinity) -> None: ...

    def delete(self, conversation_id: str) -> None: ...
