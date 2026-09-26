---
description: "Testing and validation conventions for Python, frontend, contracts, and agent behavior."
applyTo: "tests/**"
---

# Testing

- Add or update tests for changed behavior, contracts, policy decisions, routing, delegation, or stream handling.
- Prefer deterministic unit tests for policy and routing; use evaluation runs for model-dependent behavior.
- Run focused tests before the full suite. Use `uv run pytest -q` and `uv run ruff check src tests` for Python changes.
- For frontend changes, use the existing build, lint, and Playwright commands in the frontend instructions.
- Never use live credentials or production data in tests. Mock external services at the established adapter boundary.