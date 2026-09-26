# Repository Copilot Instructions

This repository uses a three-level instruction hierarchy:

1. **User level** — reusable preferences that apply across projects.
2. **Project level** — this file; repository architecture, governance, and validation requirements.
3. **Role level** — scoped `.github/instructions/*.instructions.md` files and `.github/agents/*.agent.md` files for the current task.

## Instruction precedence

When instructions conflict, apply them in this order:

1. Platform and safety requirements.
2. The user's explicit request.
3. This repository's project-level requirements.
4. The most specific applicable scoped instruction.
5. The selected specialized agent's role guidance.
6. User-level preferences and general defaults.

Use the narrowest applicable instruction. Do not copy project-specific rules into user-level instructions or repeat project rules in specialized agents.

## Working agreement

- Read the relevant ADR, contract, scoped instruction file, and nearby tests before editing.
- Prefer small, typed, testable changes. Do not invent dependencies, APIs, paths, environment variables, or deployment behavior.
- Preserve the existing layered architecture: `api` -> `application` -> ports/contracts; concrete integrations belong in `infrastructure`; wiring belongs in `bootstrap`.
- Keep authorization, guardrails, audit events, tracing, and evaluation behavior intact when changing agents, tools, routing, prompts, or models.
- Never place credentials, tokens, raw sensitive payloads, or production secrets in source, prompts, tests, logs, or documentation.
- Treat model output as untrusted data. Prompt instructions must not replace deterministic policy enforcement.

## Validation

- Run focused tests first, then `uv run pytest -q` and `uv run ruff check src tests` when practical.
- For frontend changes, run `cd src/aiweb && npm run build && npm run lint`.
- For prompt, policy, routing, model, or tool changes, run the applicable evaluation or release-gate command and record any limitation.
- For Databricks deployment changes, validate the affected bundle target before deployment.

## Change summary

Report changed files, tests/commands run, unresolved risks, and whether behavior or contracts changed. Do not claim a live Databricks or AWS validation unless it was actually performed.

## User-level template for future projects

Keep user-level instructions portable. They should contain preferences such as:

- Be concise, direct, and actionable.
- Inspect existing code and instructions before proposing changes.
- Do not invent APIs, dependencies, paths, commands, or validation results.
- Prefer small, reversible, testable changes.
- Ask one focused question only when blocked by missing information.
- Protect secrets and sensitive data.
- Report changes, validation, limitations, and unresolved risks.

Do not place Databricks, AWS, repository paths, architecture boundaries, or project commands in the user-level template.