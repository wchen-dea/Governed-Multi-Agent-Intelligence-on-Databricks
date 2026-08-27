# Context Engineering Guidelines

Hands-on conventions for controlling what information enters model context in this project. Complements [prompt-engineering-guidelines.md](prompt-engineering-guidelines.md) (how to write prompts) with rules for what context to assemble, retrieve, remember, and discard.

## Scope

Context engineering here means: which subagents/tools are visible to the orchestrator per request, what conversation state is recalled, what schema/evidence is retrieved just-in-time versus statically embedded, and what a tool result must contain to be trustworthy input for further reasoning.

For the aspirational, not-yet-implemented target-state pipeline (composite relevance scoring, ontology resolution, compression/deduplication), see [../ai-architecture-blueprint.md](../ai-architecture-blueprint.md) section 6. Do not treat that section as current behavior.

## Implemented Mechanisms and Rules

### 1. Per-request instruction assembly

- Source: `_build_base_orchestrator_instructions` in `src/aiserver/services/orchestrator_service.py`.
- Rule: the orchestrator's context is built from the live subagent config set (name, classification, evidence flag, description, `system_prompt`), not a static prompt. When adding or removing a subagent, no separate orchestrator context update is needed — the instruction text regenerates automatically.
- Cache key: `_subagent_instruction_signature` hashes the fields that affect instruction text. If you add a new field that should change routing behavior, add it to this signature or the cache will serve stale instructions.

### 2. Sticky per-conversation routing

- Source: `route_planner.py` (`_sticky_routes`, `ROUTE_STICKINESS_TTL_SECONDS`).
- Rule: a confidently matched subagent is remembered per `conversation_id` for 10 minutes so weak-overlap follow-ups stay routed to the same tool instead of re-scoring every candidate. Do not widen this TTL casually — it trades context freshness for continuity; changes need an evaluation run to confirm no routing regression.
- Rule: only store the minimal candidate identity (subagent name), never full conversation content, in the sticky-route cache.

### 3. Conversation/persona memory

- Source: `memory_service.py` (no-op and Lakebase-backed implementations), consumed in `handlers.py` to fill in a remembered persona when none is supplied.
- Rule: memory is opt-in (`MEMORY_BACKEND=lakebase`, disabled by default) and persists to a dedicated `agent_memory` database, isolated from operational data (`lakebase_ods_agent`'s `operations` database). Never point conversation memory at a data-classification tier stricter than what the memory backend is provisioned for.
- Rule: inject only the resolved persona/preference, not raw historical transcripts, unless a feature explicitly requires transcript replay and has been through a data-classification review.

### 4. Just-in-time schema/data retrieval (Lakebase)

- Source: `lakebase_ods_agent` `system_prompt`.
- Rule: never embed a full database schema statically in a prompt. Instruct the model to query `information_schema.tables`/`information_schema.columns` once, then issue the real data query — this keeps context small and prevents stale schema assumptions in the prompt.
- Rule: cap schema-discovery + data query at two calls per request (see the orchestrator's call-count limit); do not let the model loop on schema discovery.

### 5. Retrieval-grounded context with enforced provenance

- Source: `flink_support_agent`, `product_index_assistant` prompts (AI Search MCP) + `guardrails_service.py`.
- Rule: any tool whose prompt instructs citation output must have `requires_evidence: true` so the guardrail deterministically rejects ungrounded output — do not rely on the prompt alone to guarantee provenance (see [prompt-engineering-guidelines.md](prompt-engineering-guidelines.md) consistency checklist).
- Rule: for fuzzy/semantic retrieval (AI Search), require the model to state explicitly when only approximate matches were found rather than presenting them as exact.

### 6. Shared semantic context (avoid re-deriving meaning per query)

- Source: [business-semantics-metadata.md](business-semantics-metadata.md), Metric Views and AI Search indexes built by the semantics layer.
- Rule: canonical entity/metric definitions are built once and referenced by subagent prompts; do not let individual subagent prompts redefine a metric (e.g., "delight score") independently — update the shared semantics doc and propagate.

### 7. Cross-tool composite context (multi-step comparisons)

- Source: orchestrator base instructions (composite/multi-tool comparison rule) + ranked-list conventions in `sales_insights_agent`, `cdi_agent`, `lakebase_ods_agent` prompts.
- Rule: when a request needs data from two tools (e.g., cross-referencing top appointment-count stores against top sales stores), each tool must return the entity identifier alongside its ranked metric so the orchestrator can join the two result sets without a third retrieval round-trip.

## What Not to Do

- Do not add full conversation history to every orchestrator call "just in case" — this grows token cost and increases hallucination surface. Use sticky routing and persona memory instead of raw replay.
- Do not hardcode environment-specific literals (hosts, IDs) into prompt text; keep them in subagent config fields so context assembly stays declarative and auditable.
- Do not let a subagent's tool result stand as trusted input for another subagent's reasoning without the entity-identifier convention in Rule 7 — mismatched joins produce silently wrong comparisons.
- Do not increase route stickiness TTL or memory retention without checking data-classification and evaluation impact first.

## Validation After Any Context-Handling Change

```bash
uv run pytest tests/test_route_planner.py tests/test_memory_service.py tests/test_orchestrator_service.py tests/test_guardrails_service.py -q
```

## Possible Improvements to Level Up

- **Relevance scoring pipeline.** The blueprint's composite score (semantic + lexical + entity + freshness + trust + ontology distance, see [../ai-architecture-blueprint.md](../ai-architecture-blueprint.md) section 6) is not implemented. Even a lightweight version — scoring which subagent's retrieved evidence to prioritize when two tools return overlapping information — would reduce reliance on prompt-only judgment.
- **Token/context budget telemetry.** Add a metric for assembled orchestrator instruction size and per-tool result size so context growth (e.g., from adding subagents or verbose tool descriptions) is visible before it degrades latency or cost.
- **Sticky-route and memory staleness checks.** Add an automated test or monitor that flags when `ROUTE_STICKINESS_TTL_SECONDS` or memory retention settings drift from what evaluation data supports, instead of relying on manual review before changing the TTL.
- **Cross-tool join validation.** Add an eval case that exercises the composite-comparison flow (e.g., top appointment stores vs. top sales stores) end to end and asserts the orchestrator's final answer correctly identifies overlap, catching regressions in the entity-identifier convention (Rule 7).
- **Ontology/ entity resolution step.** Introduce a minimal canonical entity resolver (e.g., normalizing store IDs/names) ahead of retrieval so cross-tool joins don't silently fail on formatting mismatches (e.g., `Store 125` vs `125`).

## Related Documents

- [prompt-engineering-guidelines.md](prompt-engineering-guidelines.md)
- [agent-harness-engineering-guidelines.md](agent-harness-engineering-guidelines.md)
- [prompt-policy-controls.md](prompt-policy-controls.md)
- [data-contracts-lineage.md](data-contracts-lineage.md)
- [../architecture/tool-and-model-registry.md](../architecture/tool-and-model-registry.md)
- [../ai-architecture-blueprint.md](../ai-architecture-blueprint.md)
