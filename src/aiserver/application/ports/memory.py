"""Define conversation-memory application ports."""

from typing import Protocol


class ConversationMemory(Protocol):
    """Persist and recall conversation turns and persona preferences."""

    def save_turn(
        self, conversation_id: str, persona: str | None, role: str, content: str
    ) -> None: ...
    def recent_turns(self, conversation_id: str, limit: int) -> list[dict[str, str]]: ...
    def save_persona_preference(self, conversation_id: str, persona: str) -> None: ...
    def get_persona_preference(self, conversation_id: str) -> str | None: ...