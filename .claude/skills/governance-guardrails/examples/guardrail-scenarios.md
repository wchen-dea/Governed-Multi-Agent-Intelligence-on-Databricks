# Guardrail Scenarios

## Scenario 1: Required evidence present

- Route metadata: `requires_evidence=true`
- Response includes evidence/citation details
- Expected: pass

## Scenario 2: Required evidence missing

- Route metadata: `requires_evidence=true`
- Response omits evidence/citation details
- Expected: block with deterministic reason

## Scenario 3: Sensitive output detected

- Response includes restricted fields or unsafe content pattern
- Expected: block before response return

## Scenario 4: Allowed response for non-sensitive route

- Route metadata allows broader output
- Expected: pass without false positive block
