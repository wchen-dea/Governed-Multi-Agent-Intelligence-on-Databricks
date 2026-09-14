"""Resolve Unity Catalog registered-model routing names to serving endpoints.

Model routing settings (`MODEL_ROUTING_*`) normally hold a literal serving
endpoint name (for example `databricks-claude-sonnet-5`), which is passed
straight through to the OpenAI-compatible client. An environment may instead
point a route at a three-level Unity Catalog registered model name (for
example `catalog.schema.model_routing_default_model`); this module resolves
that name, at request time, to the serving endpoint that should currently
handle it. Resolution reads the `serving_endpoint` tag on the model's latest
version, so operators can repoint a route to a new model version (a new,
audited, UC-governed change) without redeploying the app.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

from mlflow import MlflowClient

logger = logging.getLogger(__name__)

_UC_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
_SERVING_ENDPOINT_TAG = "serving_endpoint"
# Short-lived cache so a hot request path doesn't hit the UC Model Registry on
# every turn, while still picking up a repointed model within this window.
_CACHE_TTL_SECONDS = 30.0


class ModelRouteResolutionError(RuntimeError):
    """Raise when a Unity Catalog model route cannot be resolved to an endpoint."""


@dataclass(frozen=True)
class _CacheEntry:
    endpoint_name: str
    expires_at_monotonic: float


_cache: dict[str, _CacheEntry] = {}
_cache_lock = threading.Lock()


@lru_cache(maxsize=1)
def _registry_client() -> MlflowClient:
    """Return a lazily constructed Unity Catalog model registry client."""
    return MlflowClient(registry_uri="databricks-uc")


def is_uc_model_name(model: str) -> bool:
    """Return True when `model` looks like a three-level UC name, not an endpoint name."""
    return bool(_UC_MODEL_NAME_RE.match(model.strip()))


def resolve_model_name(model: str) -> str:
    """Resolve `model` to a callable serving endpoint name.

    Literal serving endpoint names (no dots) pass through unchanged. UC
    three-level names are resolved via `_resolve_from_uc` and cached briefly.
    """
    model = model.strip()
    if not is_uc_model_name(model):
        return model

    cached = _get_cached(model)
    if cached is not None:
        return cached

    endpoint_name = _resolve_from_uc(model)
    _set_cached(model, endpoint_name)
    return endpoint_name


def _get_cached(full_name: str) -> str | None:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(full_name)
        if entry is None:
            return None
        if entry.expires_at_monotonic <= now:
            _cache.pop(full_name, None)
            return None
        return entry.endpoint_name


def _set_cached(full_name: str, endpoint_name: str) -> None:
    with _cache_lock:
        _cache[full_name] = _CacheEntry(endpoint_name, time.monotonic() + _CACHE_TTL_SECONDS)


def _resolve_from_uc(full_name: str) -> str:
    """Look up the `serving_endpoint` tag on `full_name`'s latest model version.

    `search_model_versions` results omit tags for UC-registered models (the
    client raises if you touch `.tags` on them), so the latest version number
    is looked up first and then re-fetched with `get_model_version`, which
    does return tags.
    """
    client = _registry_client()
    try:
        versions = client.search_model_versions(f"name='{full_name}'")
    except Exception as exc:
        raise ModelRouteResolutionError(
            f"Could not resolve Unity Catalog model route '{full_name}': {exc}"
        ) from exc
    if not versions:
        raise ModelRouteResolutionError(
            f"Unity Catalog model route '{full_name}' has no registered versions."
        )
    latest_version = max(int(version.version) for version in versions)
    try:
        latest = client.get_model_version(full_name, str(latest_version))
    except Exception as exc:
        raise ModelRouteResolutionError(
            f"Could not resolve Unity Catalog model route '{full_name}': {exc}"
        ) from exc
    endpoint_name = (latest.tags or {}).get(_SERVING_ENDPOINT_TAG, "").strip()
    if not endpoint_name:
        raise ModelRouteResolutionError(
            f"Unity Catalog model route '{full_name}' version {latest.version} is missing "
            f"the '{_SERVING_ENDPOINT_TAG}' tag naming its serving endpoint."
        )
    logger.info(
        "Resolved UC model route %s -> %s (version=%s)",
        full_name,
        endpoint_name,
        latest.version,
    )
    return endpoint_name
