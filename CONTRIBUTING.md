# Contributing

## Docstring Standard

Use Google-style docstrings for public modules, classes, and functions.
Prioritize operational clarity over implementation narration.

### Scope

- Required: public modules, public classes, public functions, and any private helper with non-obvious behavior.
- Optional: simple private helpers with self-explanatory names.

### Format

Use this order when sections are relevant:

1. One-line summary in imperative voice.
2. Short context paragraph for Databricks/runtime behavior.
3. `Args`.
4. `Returns`.
5. `Raises`.
6. `Side Effects`.
7. `Notes`.

### Project-Specific Requirements

- State auth expectations explicitly (`app` vs `obo`) for request- or tool-bound code.
- Document Databricks resource semantics when relevant (Genie Agent space, serving endpoint, AI Search endpoint, UC catalog/schema/table).
- Call out side effects for infra code (permissions updates, SQL grants, external API calls).
- Document idempotency expectations for scripts and deployment helpers.
- Describe failure behavior clearly (fail-open vs fail-closed and retry assumptions).

### Quality Bar

- Do not restate type hints only.
- Do not describe line-by-line implementation details.
- Keep examples realistic and target-aware (`dev`, `qa`, `stg`, `prod`).
- Update docstrings in the same change set as behavior updates.

### Function Template

```python
def example(target: str, dry_run: bool) -> dict[str, str]:
    """Apply target-scoped configuration updates.

    Args:
        target: Deployment target name (`dev`, `qa`, `stg`, or `prod`).
        dry_run: When true, report planned changes without applying updates.

    Returns:
        A summary of applied and skipped updates.

    Raises:
        ValueError: If target configuration is missing required fields.
        RuntimeError: If an external command fails.

    Side Effects:
        Writes configuration and invokes Databricks CLI commands.

    Notes:
        Designed to be idempotent when rerun with the same inputs.
    """
```