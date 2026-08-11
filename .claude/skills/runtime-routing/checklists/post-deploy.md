# Runtime Routing Post-Deploy Checklist

- Verify app deployment health is `RUNNING` and active deployment is `SUCCEEDED`.
- Execute one invoke request and one stream request.
- Validate expected route selection for representative prompts.
- Validate OBO route behavior:
  - success with forwarded token
  - explicit failure without forwarded token
- Validate policy deny behavior for disallowed persona.
- Check logs for routing, policy, and auth events.
- Confirm no startup errors or missing resource errors.
- Record verification evidence and target-specific notes.
