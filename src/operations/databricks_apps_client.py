"""Idempotent Databricks Apps lifecycle operations."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from databricks.sdk import WorkspaceClient


@dataclass(frozen=True)
class AppHealth:
    """Represent the deployable and runtime state of a Databricks App."""

    name: str
    app_state: str
    deployment_state: str
    deployment_id: str | None = None
    message: str | None = None

    @property
    def healthy(self) -> bool:
        """Return whether the App has a successful deployment and is running."""
        return self.app_state in {"RUNNING", "ACTIVE"} and self.deployment_state == "SUCCEEDED"


class DatabricksAppsClient:
    """Provide idempotent App deployment, startup, polling, and health operations.

    Args:
        workspace: Authenticated Databricks workspace client.
        sleep: Injectable sleep function for deterministic tests.
        monotonic: Injectable clock used for timeout calculations.
    """

    def __init__(
        self,
        workspace: WorkspaceClient,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.workspace = workspace
        self._sleep = sleep
        self._monotonic = monotonic

    def get(self, app_name: str) -> dict[str, Any]:
        """Return the raw App resource from the Apps REST API."""
        return self.workspace.api_client.do(
            "GET", f"/api/2.0/apps/{quote(app_name, safe='')}"
        )

    def deploy_snapshot(self, app_name: str, source_code_path: str) -> dict[str, Any]:
        """Submit an idempotent snapshot deployment for an existing App."""
        return self.workspace.api_client.do(
            "POST",
            f"/api/2.0/apps/{quote(app_name, safe='')}/deployments",
            body={"source_code_path": source_code_path, "mode": "SNAPSHOT"},
        )

    def start(self, app_name: str) -> dict[str, Any]:
        """Start an App through the Apps REST API."""
        return self.workspace.api_client.do(
            "POST", f"/api/2.0/apps/{quote(app_name, safe='')}/start", body={}
        )

    def health(self, app_name: str) -> AppHealth:
        """Return normalized App and deployment health state."""
        payload = self.get(app_name)
        deployment = payload.get("active_deployment") or {}
        deployment_status = deployment.get("status") or {}
        app_status = payload.get("app_status") or {}
        return AppHealth(
            name=app_name,
            app_state=str(app_status.get("state") or "UNKNOWN"),
            deployment_state=str(deployment_status.get("state") or "NONE"),
            deployment_id=deployment.get("deployment_id"),
            message=app_status.get("message") or deployment_status.get("message"),
        )

    def wait_for_health(
        self,
        app_name: str,
        *,
        timeout_seconds: float = 1200,
        poll_seconds: float = 5,
    ) -> AppHealth:
        """Wait until an App is healthy or its deployment reaches a terminal state.

        Raises:
            TimeoutError: If the App does not become healthy before the timeout.
            RuntimeError: If the deployment reaches a failed terminal state.
        """
        deadline = self._monotonic() + timeout_seconds
        last = self.health(app_name)
        while not last.healthy:
            if last.deployment_state in {"FAILED", "CANCELED", "TIMED_OUT"}:
                raise RuntimeError(
                    f"App deployment failed for {app_name}: "
                    f"deployment={last.deployment_state}, app={last.app_state}, "
                    f"message={last.message or 'none'}"
                )
            if self._monotonic() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for {app_name}: "
                    f"deployment={last.deployment_state}, app={last.app_state}"
                )
            self._sleep(poll_seconds)
            last = self.health(app_name)
        return last