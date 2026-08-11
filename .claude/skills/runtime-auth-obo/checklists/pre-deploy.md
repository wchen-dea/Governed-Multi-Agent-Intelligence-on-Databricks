# Runtime Auth OBO Pre-Deploy Checklist

- Confirm `auth_mode` values for affected routes.
- Confirm no required OBO route is missing token-handling tests.
- Run tests:
  - `tests/test_runtime_auth.py`
  - `tests/test_orchestrator_service.py`
  - `tests/test_subagent_config.py`
- Run `databricks bundle validate -t <target> --profile <profile>`.
- Confirm rollback plan for auth-mode edits.
