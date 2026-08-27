"""Provide service-layer helpers for orchestration and auth context building.

Naming convention: modules exposing a stateless service facade (a cohesive set
of functions/classes wired through the DI composition root) use a `*_service.py`
suffix, e.g. `orchestrator_service.py`, `policy_service.py`, `guardrails_service.py`,
`runtime_auth_service.py`, `memory_service.py`, `model_routing_service.py`,
`agent_delegation_policy_service.py`, `agent_handoff_service.py`. Infrastructure,
worker, and contract modules that aren't service facades keep a descriptive
name without the suffix, e.g. `message_bus.py`, `agent_task_bus.py`,
`agent_task_worker.py`, `route_planner.py`, `interfaces.py`.
"""
