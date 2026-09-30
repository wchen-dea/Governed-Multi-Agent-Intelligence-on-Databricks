"""MLflow delivery adapter for request-scoped identity headers."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from mlflow.genai.agent_server import get_request_headers

from aiserver.application.runtime.identity import FORWARDED_ACCESS_TOKEN_HEADER

_UNSET = object()
_forwarded_access_token_override: ContextVar[str | None | object] = ContextVar(
    "forwarded_access_token_override",
    default=_UNSET,
)


def get_forwarded_access_token() -> str | None:
    """Read and normalize the forwarded user token from MLflow request headers."""
    override = _forwarded_access_token_override.get()
    if override is not _UNSET:
        return override if isinstance(override, str) else None

    headers = get_request_headers() or {}
    token = headers.get(FORWARDED_ACCESS_TOKEN_HEADER)
    if not token:
        return None
    stripped = token.strip()
    return stripped or None


@contextmanager
def forwarded_access_token_context(token: str | None) -> Iterator[None]:
    """Expose a FastAPI-delivered user token to the governed runtime."""
    normalized = token.strip() if token else None
    reset_token = _forwarded_access_token_override.set(normalized or None)
    try:
        yield
    finally:
        _forwarded_access_token_override.reset(reset_token)
