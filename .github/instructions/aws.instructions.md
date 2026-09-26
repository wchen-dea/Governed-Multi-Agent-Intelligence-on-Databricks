---
description: "Reusable AWS AI engineering guidance for future AWS integrations in this repository."
applyTo: "src/aws/**,infra/aws/**,terraform/aws/**,resources/aws/**"
---

# AWS AI Engineering

- This repository currently has no confirmed AWS application runtime; add AWS-specific code only under an explicit AWS boundary.
- Use least-privilege IAM, encryption, private networking where required, and explicit region/account configuration.
- Prefer Bedrock model access through typed adapters and configuration, not provider-specific calls in application use cases.
- Use Secrets Manager or the approved runtime secret provider; never commit credentials or put them in prompts, logs, or `.env` files.
- Define retry, timeout, idempotency, dead-letter, and observability behavior for SQS, EventBridge, Lambda, Bedrock, and other remote calls.
- Keep cloud-neutral contracts in `application` and provider implementations in `infrastructure`.