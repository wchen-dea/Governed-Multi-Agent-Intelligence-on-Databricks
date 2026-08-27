# Prompt Engineering Guidelines

Concrete, hands-on conventions for writing and reviewing `system_prompt` and `description` fields in `src/aiserver/domain/subagents.<target>.json`, and for editing orchestrator instructions in `src/aiserver/services/orchestrator_service.py`. For the layered prompt/policy model, see [prompt-policy-controls.md](prompt-policy-controls.md).

## Scope

- Subagent `system_prompt`: model-facing instructions for a single Genie/MCP/Lakebase tool.
- Subagent `description`: orchestrator-facing routing hint used to pick the right tool.
- Orchestrator base instructions: shared routing, evidence, and delegation rules applied across all tools.

## `description` Guidelines

- Write for the orchestrator, not the end user. State what data/domain the tool covers and the concrete question types it answers.
- List capability keywords the router can match against user intent (metric names, entities, "top/bottom-N rankings", troubleshooting categories).
- Keep to 1-2 sentences. Do not duplicate the full `system_prompt`.
- When a tool supports ranking or comparison queries (e.g., "top 5 stores by X"), say so explicitly — the orchestrator uses this to decide whether a composite/cross-tool comparison is possible.

## `system_prompt` Guidelines

- Open with a role statement ("You are the ... analyst/assistant").
- State the grounding source (Genie space, AI Search index, Lakebase database) so the model doesn't fabricate scope.
- Give concrete output-shape rules: table format, column headers, units, disambiguation defaults (e.g., "use the latest available season unless specified").
- For any tool where `requires_evidence: true`, explicitly instruct the model to append citations (`[1]` style) and end with a `Source:` line. The response guardrail (`guardrails_service.py`) blocks output lacking these markers when evidence is required — the prompt and the flag must agree.
- For ranking/top-N questions, instruct the model to include the entity identifier (store ID, product ID, etc.) alongside the ranked metric so results can be cross-referenced by the orchestrator or a downstream tool call.
- For tools prone to fuzzy/approximate matches (AI Search), instruct the model to verify exact-match requests and disclose when only approximate matches were found.
- Keep ambiguity handling explicit: one clarifying question before broad/expensive analysis, not silent guessing.
- For SQL-generating tools (Lakebase), require valid SQL as the tool argument (never natural language), and define the schema-discovery-then-query fallback pattern.

## Consistency Checklist (apply across all `subagents.<target>.json` files)

Before merging a prompt/description change, verify:

1. **Evidence flag matches prompt intent.** If the prompt mandates citations, `requires_evidence` must be `true`; if the tool's output is inherently grounded (Genie SQL results) and never includes citation markers, keep it `false`. See the runbook's `evidence_required` guardrail troubleshooting section in [operations-runbook.md](../operations/operations-runbook.md).
2. **All four targets are aligned** (`subagents.dev.json`, `subagents.qa.json`, `subagents.stg.json`, `subagents.prd.json`) unless an environment-specific override is intentional and documented.
3. **Ranking/cross-reference wording is consistent** across tools that return store- or entity-level rankings, so composite queries (e.g., "top N by A, check against top M by B") can be answered by one orchestrator pass.
4. **No secrets or environment-specific literals** (hosts, tokens, connection strings) are embedded in `system_prompt` text — those belong in dedicated config fields (`pg_host`, `mcp_url`, etc.).
5. **JSON stays valid.** Validate with `python3 -c "import json; json.load(open(path))"` for each edited target file after any change.

## Orchestrator Base Instructions

Changes to shared routing/evidence/delegation rules live in `_build_base_orchestrator_instructions` in `src/aiserver/services/orchestrator_service.py`. Guidelines:

- Keep rules tool-agnostic; tool-specific behavior belongs in that subagent's `system_prompt`.
- State call-count limits explicitly (e.g., "at most once per tool, except Lakebase schema discovery + data query").
- For composite/multi-tool comparison requests, instruct the model to call each relevant tool once, gather both result sets, then compute the comparison itself before answering — do not leave this to prompt inference alone.
- For composite requests combining tools with different `freshness_sla` values, instruct the model to disclose each source's freshness next to its contribution instead of presenting a combined result as one as-of snapshot.
- Require native tool calling only; forbid pseudo-tool syntax in assistant text.
- End with the evidence/citation requirement for any tool marked `requires_evidence: true`.

## Validation After Any Prompt Change

```bash
for f in src/aiserver/domain/subagents.*.json; do python3 -c "import json; json.load(open('$f'))"; done
python -m py_compile src/aiserver/services/orchestrator_service.py
uv run pytest tests/test_subagent_config.py tests/test_guardrails_service.py tests/test_evaluation_dataset_sync.py tests/test_orchestrator_service.py -q
```

## Possible Improvements to Level Up

- **Automated consistency linter.** Script a CI check that parses all `subagents.<target>.json` files and fails if a `system_prompt` mentions citations/`Source:` while `requires_evidence` is `false` (or vice versa) — this session's `flink_support_agent` mismatch would have been caught automatically instead of by manual review.
- **Cross-target diff check.** Add a test asserting `system_prompt`/`description` text is identical across dev/qa/stg/prd unless a documented environment-specific override exists, to prevent silent drift between targets.
- **Golden-prompt regression tests.** Snapshot-test the assembled orchestrator instructions (`_build_base_orchestrator_instructions` output) so an unintended wording change is visible in a diff, not just in eval scores.
- **Prompt versioning/changelog.** Track `system_prompt` revisions with a short version marker or changelog entry per subagent so eval regressions can be bisected to a specific prompt edit.
- **Externalize repeated phrasing.** Several prompts repeat similar clauses (ranking/cross-reference wording, evidence mandate wording); consider a small templating helper so these shared clauses are defined once and interpolated, reducing copy/paste drift across the 4 target files.

## Related Documents

- [prompt-policy-controls.md](prompt-policy-controls.md)
- [context-engineering-guidelines.md](context-engineering-guidelines.md)
- [agent-harness-engineering-guidelines.md](agent-harness-engineering-guidelines.md)
- [../operations/operations-runbook.md](../operations/operations-runbook.md)
- [../architecture/tool-and-model-registry.md](../architecture/tool-and-model-registry.md)
- [../adrs/0005-governed-routing-policy-and-response-guardrails.md](../adrs/0005-governed-routing-policy-and-response-guardrails.md)
