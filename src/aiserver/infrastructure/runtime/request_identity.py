"""MLflow delivery adapter for request-scoped identity headers."""

from mlflow.genai.agent_server import get_request_headers

from aiserver.application.runtime.identity import FORWARDED_ACCESS_TOKEN_HEADER


def get_forwarded_access_token() -> str | None:
    """Read and normalize the forwarded user token from MLflow request headers."""
    headers = get_request_headers() or {}
    token = headers.get(FORWARDED_ACCESS_TOKEN_HEADER)
    if not token:
        return None
    stripped = token.strip()
    return stripped or None
