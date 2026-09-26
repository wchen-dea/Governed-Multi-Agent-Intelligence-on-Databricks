# Runtime Guardrails Post-Deploy Checklist

- Confirm app health is `RUNNING`.
- Run one pass scenario and one block scenario.
- Validate deterministic block reason for denied output.
- Validate no unexpected false-positive blocks on allowed routes.
- Check logs for guardrail decision events.
- Record test evidence for target.
