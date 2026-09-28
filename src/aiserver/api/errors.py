"""Consistent public API error handling."""

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str
    status_code: int


def error_response(request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        headers={"X-Request-ID": getattr(request.state, "request_id", "")},
    )
