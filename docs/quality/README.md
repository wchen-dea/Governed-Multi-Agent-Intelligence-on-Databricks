# Quality Guide

## Scope

This section owns evaluation design, scorers, KPI thresholds, and promotion evidence. Current architecture facts are maintained in [runtime technical specifications](../architecture/runtime-technical-specs.md); operational execution is covered by the [MLflow guide](../operations/mlflow-guide.md).

## Primary Document

- [Evaluation specification](evaluation-spec.md): datasets, scorer definitions, release-gate semantics, model experiment plan, and current evidence.

## Current Gate

Promotion is blocked until `ToolCallCorrectness >= 0.800`. The currently documented evidence is `ToolCallCorrectness = 0.400`. Route-plan metadata and unit tests do not prove live model tool-call correctness.
