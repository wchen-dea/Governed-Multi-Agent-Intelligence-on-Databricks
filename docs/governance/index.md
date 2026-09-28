# Governance Guide

## Scope

This section defines policy intent, data semantics, lineage expectations, and security controls. Current runtime behavior is authoritative in [architecture runtime technical specifications](../architecture/runtime-specification.md); this section distinguishes implemented controls from target-state governance practices.

## Ownership

| Document | Owns |
| --- | --- |
| [Prompt policy controls](prompt-policy.md) | Prompt layers, policy checks, and guardrail intent |
| [Prompt engineering guidelines](prompt-engineering.md) | Hands-on conventions for writing/reviewing subagent prompts and descriptions |
| [Context engineering guidelines](context-engineering.md) | Conventions for what context to assemble, retrieve, remember, and discard |
| [Agent harness engineering guidelines](agent-harness-guidelines.md) | Conventions for request pipeline, execution contracts, delegation, and observability plumbing |
| [Human-in-the-loop approval](human-approval.md) | Manager approval state, decision API, persistence, and operational dispatch boundary |
| [Data contracts and lineage](data-contracts-and-lineage.md) | Data boundaries, lifecycle lineage, and contract expectations |
| [Business semantics metadata](business-semantics.md) | Domain definitions and metadata expectations |
| [Security threat model](security-threat-model.md) | Threats, trust boundaries, and hardening priorities |

## Reading Path

1. [Security threat model](security-threat-model.md)
2. [Prompt policy controls](prompt-policy.md)
3. [Prompt engineering guidelines](prompt-engineering.md)
4. [Context engineering guidelines](context-engineering.md)
5. [Agent harness engineering guidelines](agent-harness-guidelines.md)
6. [Human-in-the-loop approval](human-approval.md)
7. [Data contracts and lineage](data-contracts-and-lineage.md)
8. [Business semantics metadata](business-semantics.md)

## Current Boundary

Implemented controls include persona and auth-mode policy filtering, classification-aware routing, input/output guardrails, lifecycle audit events, Unity Catalog boundaries, and the store-intervention HITL approval flow. Broader approval workflows and dispatch integrations remain target-state extensions unless an architecture or operations document explicitly marks them as implemented.
