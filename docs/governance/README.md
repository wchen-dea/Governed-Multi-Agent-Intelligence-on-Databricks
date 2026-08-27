# Governance Guide

## Scope

This section defines policy intent, data semantics, lineage expectations, and security controls. Current runtime behavior is authoritative in [architecture runtime technical specifications](../architecture/runtime-technical-specs.md); this section distinguishes implemented controls from target-state governance practices.

## Ownership

| Document | Owns |
| --- | --- |
| [Prompt policy controls](prompt-policy-controls.md) | Prompt layers, policy checks, and guardrail intent |
| [Prompt engineering guidelines](prompt-engineering-guidelines.md) | Hands-on conventions for writing/reviewing subagent prompts and descriptions |
| [Context engineering guidelines](context-engineering-guidelines.md) | Conventions for what context to assemble, retrieve, remember, and discard |
| [Agent harness engineering guidelines](agent-harness-engineering-guidelines.md) | Conventions for request pipeline, execution contracts, delegation, and observability plumbing |
| [Data contracts and lineage](data-contracts-lineage.md) | Data boundaries, lifecycle lineage, and contract expectations |
| [Business semantics metadata](business-semantics-metadata.md) | Domain definitions and metadata expectations |
| [Security threat model](security-threat-model.md) | Threats, trust boundaries, and hardening priorities |

## Reading Path

1. [Security threat model](security-threat-model.md)
2. [Prompt policy controls](prompt-policy-controls.md)
3. [Prompt engineering guidelines](prompt-engineering-guidelines.md)
4. [Context engineering guidelines](context-engineering-guidelines.md)
5. [Agent harness engineering guidelines](agent-harness-engineering-guidelines.md)
6. [Data contracts and lineage](data-contracts-lineage.md)
7. [Business semantics metadata](business-semantics-metadata.md)

## Current Boundary

Implemented controls include persona and auth-mode policy filtering, classification-aware routing, input/output guardrails, lifecycle audit events, and Unity Catalog boundaries. Proposed metadata envelopes, human approvals, and broader release processes remain target-state practices unless an architecture or operations document explicitly marks them as implemented.
