# ADR 0001: Use Ownership-Based Backend Architecture

## Status

Accepted

## Context

The original layered package structure grouped unrelated runtime concerns under
`services` and `shared`. As the runtime added request-time orchestration,
Databricks adapters, persistence, tracing, and operational workflows, those
catch-all layers obscured dependency ownership and made extension points harder
to discover.

## Decision

Use explicit ownership-based packages under `src/aiserver/`:

```text
src/aiserver/
├── api/              # HTTP and MLflow Agent Server delivery
├── application/      # Auth, orchestration, delegation, guardrails, ports, runtime helpers
├── bootstrap/        # Concrete dependency composition
├── config/           # Dependency-neutral environment settings
├── contracts/        # Typed execution, delegation, and subagent registry contracts
└── infrastructure/   # Databricks, messaging, observability, and persistence adapters
```

Dependencies flow inward: `api -> application -> contracts/config`.
Infrastructure implements application ports, and `bootstrap` is the only
composition root. `application` must not import `api`, `bootstrap`, or
`infrastructure`.

## Alternatives Considered

- Retain the `services` and `shared` layers with stricter naming conventions.
- Collapse all runtime code into feature-oriented packages without ports.
- Split the backend into independently deployed services.

## Consequences

### Positive

- Package names identify ownership and extension boundaries directly.
- Application use cases can be tested without concrete Databricks adapters.
- Infrastructure adapters can evolve without leaking into request-time logic.

### Trade-offs

- More explicit imports and package boundaries to maintain.
- Refactors must update package-sensitive documentation, skills, and deployment paths.

## Implementation Notes

- Package and dependency map: [layered agentic architecture](../architecture/layered-agentic-architecture.md)
- Composition root: [src/aiserver/bootstrap/container.py](../../src/aiserver/bootstrap/container.py)
- Boundary enforcement: [tests/test_layer_isolation.py](../../tests/test_layer_isolation.py)