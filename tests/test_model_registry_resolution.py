"""Tests for Unity Catalog model-route resolution."""

from dataclasses import dataclass, field

import pytest

from aiserver.application.orchestration import model_registry
from aiserver.application.orchestration.model_registry import (
    ModelRouteResolutionError,
    is_uc_model_name,
    resolve_model_name,
)


@dataclass
class _FakeModelVersionStub:
    """Mimic `ModelVersionSearch`: has a version but no tags."""

    version: str


@dataclass
class _FakeModelVersion:
    """Mimic `ModelVersion`: the full object returned by `get_model_version`."""

    version: str
    tags: dict[str, str] = field(default_factory=dict)


class _FakeRegistryClient:
    def __init__(self, versions: list[_FakeModelVersion]):
        self.versions_by_number = {version.version: version for version in versions}
        self.search_calls = 0

    def search_model_versions(self, _filter_string: str) -> list[_FakeModelVersionStub]:
        self.search_calls += 1
        return [_FakeModelVersionStub(version=v) for v in self.versions_by_number]

    def get_model_version(self, _full_name: str, version: str) -> _FakeModelVersion:
        return self.versions_by_number[version]


@pytest.fixture(autouse=True)
def _clear_cache():
    model_registry._cache.clear()
    yield
    model_registry._cache.clear()


def test_is_uc_model_name_detects_three_level_names():
    assert is_uc_model_name("quickstart_catalog.multi_agent_schema.model_routing_default_model")
    assert not is_uc_model_name("databricks-claude-sonnet-5")
    assert not is_uc_model_name("system.ai")


def test_resolve_model_name_passes_through_literal_endpoint_names(monkeypatch):
    def _fail_if_called():
        raise AssertionError("registry client should not be constructed for literal names")

    monkeypatch.setattr(model_registry, "_registry_client", _fail_if_called)

    assert resolve_model_name("databricks-claude-sonnet-5") == "databricks-claude-sonnet-5"


def test_resolve_model_name_reads_serving_endpoint_tag_from_latest_version(monkeypatch):
    client = _FakeRegistryClient(
        [
            _FakeModelVersion(version="1", tags={"serving_endpoint": "old-endpoint"}),
            _FakeModelVersion(version="2", tags={"serving_endpoint": "new-endpoint"}),
        ]
    )
    monkeypatch.setattr(model_registry, "_registry_client", lambda: client)

    resolved = resolve_model_name("quickstart_catalog.multi_agent_schema.model_routing_default_model")

    assert resolved == "new-endpoint"


def test_resolve_model_name_caches_within_ttl(monkeypatch):
    client = _FakeRegistryClient(
        [_FakeModelVersion(version="1", tags={"serving_endpoint": "cached-endpoint"})]
    )
    monkeypatch.setattr(model_registry, "_registry_client", lambda: client)
    full_name = "quickstart_catalog.multi_agent_schema.model_routing_default_model"

    assert resolve_model_name(full_name) == "cached-endpoint"
    assert resolve_model_name(full_name) == "cached-endpoint"
    assert client.search_calls == 1


def test_resolve_model_name_raises_when_no_versions_registered(monkeypatch):
    monkeypatch.setattr(model_registry, "_registry_client", lambda: _FakeRegistryClient([]))

    with pytest.raises(ModelRouteResolutionError, match="no registered versions"):
        resolve_model_name("quickstart_catalog.multi_agent_schema.model_routing_default_model")


def test_resolve_model_name_raises_when_serving_endpoint_tag_missing(monkeypatch):
    client = _FakeRegistryClient([_FakeModelVersion(version="1", tags={})])
    monkeypatch.setattr(model_registry, "_registry_client", lambda: client)

    with pytest.raises(ModelRouteResolutionError, match="missing the 'serving_endpoint' tag"):
        resolve_model_name("quickstart_catalog.multi_agent_schema.model_routing_default_model")


def test_resolve_model_name_wraps_registry_errors(monkeypatch):
    class _BrokenClient:
        def search_model_versions(self, _filter_string: str):
            raise RuntimeError("permission denied")

    monkeypatch.setattr(model_registry, "_registry_client", lambda: _BrokenClient())

    with pytest.raises(ModelRouteResolutionError, match="Could not resolve"):
        resolve_model_name("quickstart_catalog.multi_agent_schema.model_routing_default_model")
