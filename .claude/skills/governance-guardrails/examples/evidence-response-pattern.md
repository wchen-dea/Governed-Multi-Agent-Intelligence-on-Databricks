# Evidence Response Pattern

Use this pattern for routes that require evidence-backed output.

## Required response traits

- Answer includes factual statement tied to retrieved context.
- Evidence section includes source identifiers or citations.
- Missing evidence triggers guardrail block outcome.

## Minimal acceptance example

- `answer`: concise user-facing response
- `evidence`: list of source identifiers and short rationale
- `confidence`: optional confidence score for review workflows
