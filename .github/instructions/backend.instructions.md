---
description: "Backend conventions for the FastAPI and MLflow Agent Server runtime."
applyTo: "src/aiserver/**,src/operations/**"
---

# Backend

- Keep API handlers thin: parse, normalize, invoke an application use case, and shape the response.
- `application` must not import `api`, `bootstrap`, or `infrastructure`.
- Use existing Pydantic contracts and ports; do not pass ad hoc dictionaries across layers.
- Route policy before tool execution and response guardrails after model output.
- Preserve invoke and stream parity, structured failure statuses, lifecycle events, and MLflow trace metadata.
- Verify dependencies in `pyproject.toml` before adding libraries. Use `uv` for Python commands.