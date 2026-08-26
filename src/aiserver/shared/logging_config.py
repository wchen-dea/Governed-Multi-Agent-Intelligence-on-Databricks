"""Centralized logging setup for backend app processes."""

import logging

from backend.shared.settings import AppSettings

_CONFIGURED = False


def _to_log_level(level_name: str) -> int:
    """Convert a log-level name to logging module constant safely."""
    return getattr(logging, level_name.upper(), logging.INFO)


def configure_logging(settings: AppSettings) -> None:
    """Configure root and package loggers once for consistent backend logging."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = _to_log_level(settings.log_level)
    formatter = logging.Formatter(
        fmt=settings.log_format,
        datefmt=settings.log_date_format,
    )

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format=settings.log_format,
            datefmt=settings.log_date_format,
        )
    else:
        root.setLevel(level)
        for handler in root.handlers:
            handler.setLevel(level)
            handler.setFormatter(formatter)

    # Keep noisy MLflow autologging internals out of normal application logs.
    logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)
    _CONFIGURED = True
