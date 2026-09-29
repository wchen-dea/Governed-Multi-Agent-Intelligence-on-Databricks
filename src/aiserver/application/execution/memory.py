"""Conversation-memory behavior for governed execution."""

from aiserver.application.ports.memory import ConversationMemory
from aiserver.contracts.execution import ExecutionMessage, GovernedExecutionRequest


def hydrate_request(
    request: GovernedExecutionRequest,
    memory: ConversationMemory,
    *,
    max_turns: int,
) -> GovernedExecutionRequest:
    """Apply remembered persona and prepend non-duplicated conversation turns."""
    conversation_id = request.conversation_id
    if not conversation_id:
        return request

    persona = request.persona or memory.get_persona_preference(conversation_id)
    messages = request.messages
    if max_turns > 0:
        remembered = tuple(
            ExecutionMessage(role=turn["role"], content=turn["content"])
            for turn in memory.recent_turns(conversation_id, max_turns)
            if turn.get("role") in {"user", "assistant"} and turn.get("content")
        )
        if remembered and not _contains_sequence(messages, remembered):
            messages = (*remembered, *messages)

    return GovernedExecutionRequest(
        messages=messages,
        conversation_id=conversation_id,
        persona=persona,
        metadata=request.metadata,
    )


def persist_turns(
    request: GovernedExecutionRequest,
    memory: ConversationMemory,
    *,
    answer: str,
) -> None:
    """Persist the latest user question, answer, and persona preference."""
    conversation_id = request.conversation_id
    if not conversation_id:
        return
    question = latest_user_question(request)
    if question:
        memory.save_turn(conversation_id, request.persona, "user", question)
    if answer:
        memory.save_turn(conversation_id, request.persona, "assistant", answer)
    if request.persona:
        memory.save_persona_preference(conversation_id, request.persona)


def latest_user_question(request: GovernedExecutionRequest) -> str:
    """Return the latest normalized user message."""
    for message in reversed(request.messages):
        if message.role == "user":
            return message.content
    return ""


def last_assistant_text(output_items: tuple[dict[str, object], ...]) -> str:
    """Extract the final assistant text from output items."""
    for item in reversed(output_items):
        if item.get("role") != "assistant":
            continue
        content = item.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            ).strip()
    return ""


def _contains_sequence(
    messages: tuple[ExecutionMessage, ...],
    candidate: tuple[ExecutionMessage, ...],
) -> bool:
    if len(candidate) > len(messages):
        return False
    return any(
        messages[index : index + len(candidate)] == candidate
        for index in range(len(messages) - len(candidate) + 1)
    )
