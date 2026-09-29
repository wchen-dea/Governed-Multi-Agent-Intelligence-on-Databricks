from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from aiserver.config.settings import AppSettings
from aiserver.contracts.execution import RouteAffinity
from aiserver.infrastructure.persistence.routing import (
    InMemoryRouteAffinityStore,
    LakebaseRouteAffinityStore,
    NoopRouteAffinityStore,
    default_route_affinity_store,
)


class _FakeCursor:
    def __init__(self, records: dict[str, tuple[list[str], datetime]]) -> None:
        self._records = records
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement: str, params: tuple = ()) -> None:
        normalized = statement.strip().lower()
        if normalized.startswith("insert into"):
            conversation_id, candidate_names, expires_at = params
            import json

            self._records[conversation_id] = (json.loads(candidate_names), expires_at)
        elif normalized.startswith("delete from"):
            conversation_id = params[0]
            if "expires_at <= now()" not in normalized:
                self._records.pop(conversation_id, None)
            elif (
                conversation_id in self._records
                and self._records[conversation_id][1] <= datetime.now(UTC)
            ):
                self._records.pop(conversation_id)
        elif normalized.startswith("select candidate_names"):
            record = self._records.get(params[0])
            self._result = record

    def fetchone(self):
        return self._result


class _FakeConnection:
    def __init__(self, records: dict[str, tuple[list[str], datetime]]) -> None:
        self._records = records

    def cursor(self):
        return _FakeCursor(self._records)

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


def _build_lakebase_store(records) -> LakebaseRouteAffinityStore:
    with patch(
        "aiserver.infrastructure.persistence.routing.connect_lakebase",
        side_effect=lambda *args, **kwargs: _FakeConnection(records),
    ):
        return LakebaseRouteAffinityStore(
            project_id="project",
            branch_id="branch",
            endpoint_id="endpoint",
            database="database",
            pg_host="host",
            pg_user="user",
            table="agent_route_affinity",
            workspace_client=MagicMock(),
        )


def test_in_memory_store_expires_records():
    store = InMemoryRouteAffinityStore()
    store.put(
        RouteAffinity(
            conversation_id="expired",
            candidate_names=("sales",),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )

    assert store.get("expired") is None


def test_lakebase_store_upserts_reads_and_deletes_affinity():
    records = {}
    store = _build_lakebase_store(records)
    affinity = RouteAffinity(
        conversation_id="conv-1",
        candidate_names=("sales", "inventory"),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    with patch(
        "aiserver.infrastructure.persistence.routing.connect_lakebase",
        side_effect=lambda *args, **kwargs: _FakeConnection(records),
    ):
        store.put(affinity)
        assert store.get("conv-1") == affinity
        store.delete("conv-1")
        assert store.get("conv-1") is None


def test_lakebase_store_rejects_unsafe_table_name():
    with pytest.raises(ValueError, match="valid SQL identifier"):
        LakebaseRouteAffinityStore(
            project_id="project",
            branch_id="branch",
            endpoint_id="endpoint",
            database="database",
            pg_host="host",
            pg_user="user",
            table="route-affinity; DROP TABLE users",
            workspace_client=MagicMock(),
        )


def test_default_route_affinity_store_selects_supported_backends():
    assert isinstance(
        default_route_affinity_store(AppSettings(route_affinity_backend="disabled")),
        NoopRouteAffinityStore,
    )
    assert isinstance(
        default_route_affinity_store(AppSettings(route_affinity_backend="memory")),
        InMemoryRouteAffinityStore,
    )


def test_default_route_affinity_store_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unsupported ROUTE_AFFINITY_BACKEND"):
        default_route_affinity_store(AppSettings(route_affinity_backend="unknown"))
