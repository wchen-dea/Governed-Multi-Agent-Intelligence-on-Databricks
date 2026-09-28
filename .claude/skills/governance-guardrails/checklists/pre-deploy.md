# Runtime Guardrails Pre-Deploy Checklist

- Confirm target/profile selection.
- Confirm updated guardrail rules are documented.
- Confirm `requires_evidence` metadata is present where needed.
- Run tests:
  - `tests/test_guardrails_service.py`
  - `tests/test_policy_service.py`
  - `tests/test_orchestrator_service.py`
- Run `databricks bundle validate -t <target> --profile <profile>`.
- Confirm rollback notes are prepared.
