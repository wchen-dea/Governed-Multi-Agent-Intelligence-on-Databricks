# Runtime Auth OBO Post-Deploy Checklist

- Verify OBO success path with forwarded token.
- Verify OBO failure path without token.
- Verify APP route success path without forwarded token.
- Confirm no silent fallback from OBO to APP.
- Review auth-related runtime logs and error messages.
