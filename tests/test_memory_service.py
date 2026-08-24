from unittest.mock import MagicMock, patch

import pytest

from backend.services.memory_service import (
    LakebaseConversationMemory,
    NoopConversationMemory,
    default_conversation_memory,
)
from backend.shared.settings import AppSettings


def _settings(**kwargs) -> AppSettings:
    values = AppSettings().__dict__.copy()
    values.update(kwargs)
    return AppSettings(**values)


class _FakeCursor:
    def __init__(self, store: dict) -> None:
        self._store = store
        self._last_result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement: str, params: tuple = ()) -> None:
        statement_lower = statement.strip().lower()
        if statement_lower.startswith("insert into") and "conversations" in statement_lower:
            conversation_id, persona, role, content = params
            self._store.setdefault("turns", []).append(
                {"conversation_id": conversation_id, "persona": persona, "role": role, "content": content}
            )
        elif statement_lower.startswith("select role, content"):
            conversation_id, limit = params
            rows = [
                (t["role"], t["content"])
                for t in self._store.get("turns", [])
                if t["conversation_id"] == conversation_id
            ]
            self._last_result = list(reversed(rows[-limit:]))
        elif statement_lower.startswith("insert into") and "preferences" in statement_lower:
            conversation_id, persona = params
            self._store.setdefault("preferences", {})[conversation_id] = persona
        elif statement_lower.startswith("select persona"):
            (conversation_id,) = params
            persona = self._store.get("preferences", {}).get(conversation_id)
            self._last_result = [(persona,)] if persona else []

    def fetchall(self):
        return self._last_result or []

    def fetchone(self):
        return self._last_result[0] if self._last_result else None


class _FakeConnection:
    def __init__(self, store: dict) -> None:
        self._store = store

    def cursor(self):
        return _FakeCursor(self._store)

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.fixture
def memory_store():
    return {}


def _build_memory(memory_store, **overrides) -> LakebaseConversationMemory:
    with patch("backend.services.memory_service.connect_lakebase") as connect_mock:
        connect_mock.side_effect = lambda *a, **k: _FakeConnection(memory_store)
        kwargs = {
            "project_id": "proj",
            "branch_id": "main",
            "endpoint_id": "primary",
            "database": "db",
            "pg_host": "host",
            "pg_user": "user",
            "conversation_table": "agent_memory_conversations",
            "preference_table": "agent_memory_preferences",
            "fail_open": True,
            "workspace_client": MagicMock(),
        }
        kwargs.update(overrides)
        return LakebaseConversationMemory(**kwargs)


def test_save_and_recall_turns(memory_store):
    memory = _build_memory(memory_store)
    with patch("backend.services.memory_service.connect_lakebase") as connect_mock:
        connect_mock.side_effect = lambda *a, **k: _FakeConnection(memory_store)
        memory.save_turn("conv-1", "manager", "user", "hello")
        memory.save_turn("conv-1", "manager", "assistant", "hi there")
        turns = memory.recent_turns("conv-1", limit=10)

    assert turns == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]


def test_save_and_get_persona_preference(memory_store):
    memory = _build_memory(memory_store)
    with patch("backend.services.memory_service.connect_lakebase") as connect_mock:
        connect_mock.side_effect = lambda *a, **k: _FakeConnection(memory_store)
        memory.save_persona_preference("conv-1", "analyst")
        assert memory.get_persona_preference("conv-1") == "analyst"
        assert memory.get_persona_preference("conv-unknown") is None


def test_lakebase_memory_requires_connection_fields():
    with pytest.raises(ValueError):
        LakebaseConversationMemory(
            project_id="",
            branch_id="main",
            endpoint_id="primary",
            database="db",
            pg_host="host",
            pg_user="user",
            conversation_table="t",
            preference_table="p",
            fail_open=True,
            workspace_client=MagicMock(),
        )


def test_lakebase_memory_fail_open_swallows_errors(memory_store):
    memory = _build_memory(memory_store)
    with patch("backend.services.memory_service.connect_lakebase") as connect_mock:
        connect_mock.side_effect = RuntimeError("connection refused")
        memory.save_turn("conv-1", "manager", "user", "hello")
        assert memory.recent_turns("conv-1", limit=10) == []
        assert memory.get_persona_preference("conv-1") is None


def test_default_conversation_memory_disabled_backend():
    memory = default_conversation_memory(_settings(memory_backend="disabled"))
    assert isinstance(memory, NoopConversationMemory)


def test_default_conversation_memory_unknown_backend_falls_back_to_noop():
    memory = default_conversation_memory(_settings(memory_backend="unknown"))
    assert isinstance(memory, NoopConversationMemory)


def test_default_conversation_memory_lakebase_missing_config_falls_back_to_noop():
    memory = default_conversation_memory(
        _settings(memory_backend="lakebase", memory_fail_open=True)
    )
    assert isinstance(memory, NoopConversationMemory)


def test_default_conversation_memory_lakebase_missing_config_raises_when_not_fail_open():
    with pytest.raises(ValueError):
        default_conversation_memory(
            _settings(memory_backend="lakebase", memory_fail_open=False)
        )


def test_noop_conversation_memory_is_inert():
    memory = NoopConversationMemory()
    memory.save_turn("conv-1", "manager", "user", "hello")
    memory.save_persona_preference("conv-1", "manager")
    assert memory.recent_turns("conv-1", limit=10) == []
    assert memory.get_persona_preference("conv-1") is None
