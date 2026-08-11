# Runtime Routing Pre-Deploy Checklist

- Confirm target and profile are correct (`dev`, `qa`, `stg`, `prod`).
- Confirm route IDs/names are real values (no placeholders for promoted targets).
- Confirm `auth_mode` is set per route and reviewed.
- Confirm persona and classification metadata are present.
- Confirm routing changes are documented in model/tool registry.
- Run tests:
  - `tests/test_subagent_config.py`
  - `tests/test_orchestrator_service.py`
  - `tests/test_policy_service.py`
  - `tests/test_runtime_auth.py`
- Run bundle validation:
  - `databricks bundle validate -t <target> --profile <profile>`
- Confirm rollback plan exists for modified routes.
