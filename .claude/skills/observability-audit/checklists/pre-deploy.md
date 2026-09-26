# Runtime Audit Observability Pre-Deploy Checklist

- Confirm selected backend and required env/config values.
- Confirm UC audit placeholders are replaced for promoted targets.
- Run tests:
  - `tests/test_message_bus_backends.py`
  - `tests/test_message_bus_integration.py`
- Run `databricks bundle validate -t <target> --profile <profile>`.
- Confirm fallback behavior (fail-open/fail-closed) is documented.
