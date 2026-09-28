# Runtime Audit Observability Post-Deploy Checklist

- Confirm app health and startup stability.
- Trigger one invoke request and verify lifecycle event emission.
- Verify backend-specific publish behavior (including async mode if enabled).
- For `uc_table`, verify rows are written to expected catalog/schema/table.
- Capture logs or query evidence for release records.
