# Business Semantics and AI Metadata Spec

Define the minimum reliable business semantics and AI metadata required to keep routing, safety, evaluation, and audit behavior stable.

## Purpose

Provide a production-grade metadata contract that can be enforced at runtime and at release gates.

## Why This Matters

Reliable semantics and metadata directly impact these system dimensions:

- Routing accuracy: correct tool and domain selection.
- Response consistency: same question yields same business meaning.
- Safety and compliance: policy checks can enforce data and role constraints.
- Explainability and trust: every answer is traceable to evidence and lineage.
- Evaluation reliability: KPI trends are meaningful across releases.
- Cost and performance: metadata-aware routing reduces unnecessary tool calls.

## Canonical Business Semantics Contract

Each domain, tool, and response must align to the canonical business semantics below.

### 1. Entity Semantics

Required canonical entities (extend as needed):

- customer
- order
- store
- sku
- supplier
- region

Rules:

- Each entity must have a single canonical identifier and owner.
- Synonyms must map to a canonical entity name.
- Cross-domain entity joins must be explicitly documented.

### 2. Metric Semantics

Required canonical metrics (extend as needed):

- revenue
- gross_margin
- fill_rate
- stockout_rate
- on_time_delivery

Rules:

- Each metric must include formula, grain, and allowed dimensions.
- Metric definition changes require version bump and release note.

### 3. Time Semantics

Rules:

- Define fiscal calendar and business-day rules.
- Define data freshness window and SLA per domain.
- Define reporting cutoff timestamp and timezone.

### 4. Policy Semantics

Rules:

- Role and persona access must map to data classifications.
- Purpose-of-use constraints must be explicit for sensitive domains.
- Deny behavior must be deterministic and user-readable.

## AI Metadata Contract

This contract is mandatory for every subagent/tool route.

### Tool and Domain Metadata Schema

```json
{
  "tool_id": "string",
  "owner": {
    "business": "string",
    "technical": "string"
  },
  "data_classification": "public|internal|confidential|restricted",
  "allowed_personas": ["string"],
  "auth_mode": "app|obo",
  "freshness_sla": {
    "max_age_minutes": 1440,
    "update_cadence": "hourly|daily|weekly",
    "timezone": "UTC"
  },
  "source_of_truth": {
    "domain": "string",
    "dataset": "string",
    "version": "string"
  },
  "business_semantics_ref": {
    "entities": ["string"],
    "metrics": ["string"],
    "definitions_version": "string"
  },
  "requires_evidence": true
}
```

### Response Metadata Schema

```json
{
  "request_id": "string",
  "policy_decision_id": "string",
  "lineage_id": "string",
  "tool_calls": [
    {
      "tool_name": "string",
      "source": "genie|serving_endpoint|app|mcp|lakebase",
      "query_or_operation_id": "string"
    }
  ],
  "confidence": {
    "score": 0.0,
    "band": "low|medium|high"
  },
  "evidence": [
    {
      "citation": "string",
      "source_type": "table|doc|api",
      "source_ref": "string"
    }
  ],
  "guardrail": {
    "blocked": false,
    "reasons": []
  }
}
```

### Runtime and Release Metadata

```json
{
  "model_version": "string",
  "prompt_version": "string",
  "policy_version": "string",
  "guardrail_version": "string",
  "evaluation": {
    "tool_call_accuracy": 0.0,
    "auth_correctness": 0.0,
    "safety": 0.0,
    "groundedness": 0.0,
    "passed": true
  }
}
```

## Validation Checklist

### Runtime Validation (Request Time)

For each selected route/tool:

1. Metadata completeness: owner, classification, personas, freshness SLA present.
2. Persona authorization: requester persona in allowed_personas.
3. Auth mode safety: OBO routes require forwarded user identity.
4. Classification policy: requested operation allowed for classification level.
5. Semantics reference: route declares entities/metrics definitions version.

Mandatory deny reasons:

- metadata_missing
- persona_not_allowed
- missing_obo_identity
- classification_restricted
- semantics_version_unresolved

### Runtime Validation (Response Time)

1. Response metadata includes policy_decision_id and lineage_id.
2. Evidence present when requires_evidence is true.
3. Confidence required for sensitive classifications.
4. Guardrail result emitted with blocked flag and reasons.

Mandatory block reasons:

- evidence_required
- low_confidence_sensitive
- unsafe_output
- lineage_missing

### Release-Gate Validation

1. All active tools/routes have complete metadata contract.
2. No unresolved entity/metric semantics references.
3. Evaluation KPIs meet thresholds:
   - tool_call_accuracy
   - auth_correctness
   - safety
   - groundedness
4. Model/prompt/policy/guardrail versions are stamped and immutable for release.
5. Regression report includes failures by persona and data classification slices.

Hard-fail release if any of the following is true:

- required metadata field missing in active route
- evidence-required route lacks evidence in golden eval tests
- any KPI below threshold
- missing version stamp for model or policy layers

## Implementation Mapping

Current repository components aligned to this spec:

- Route metadata and validation: `src/aiserver/domain/subagent_config.py`
- Request-time policy enforcement: `src/aiserver/services/policy_service.py`
- Runtime auth enforcement: `src/aiserver/services/runtime_auth_service.py`
- Response guardrails: `src/aiserver/services/guardrails_service.py`
- Lifecycle and lineage events: `src/aiserver/services/message_bus.py`
- Release gate evaluation: `src/aiserver/evaluate_agent.py`

## Adoption Plan

1. Add missing metadata fields to all active subagents.
2. Enforce metadata completeness before tool registration.
3. Attach response metadata envelope in handler responses.
4. Add validation tests for metadata completeness and deny reason coverage.
5. Add release-gate check for metadata-contract compliance.

## Related Documents

- data-contracts-lineage.md
- prompt-policy-controls.md
- security-threat-model.md
- ../architecture/tool-and-model-registry.md
- ../quality/evaluation-spec.md