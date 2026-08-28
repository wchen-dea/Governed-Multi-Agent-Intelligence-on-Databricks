"""Provide shared MLflow trace metadata integration."""

import mlflow


def update_trace_metadata(metadata: dict[str, str]) -> None:
    """Write metadata to the active MLflow trace."""
    mlflow.update_current_trace(metadata=metadata)