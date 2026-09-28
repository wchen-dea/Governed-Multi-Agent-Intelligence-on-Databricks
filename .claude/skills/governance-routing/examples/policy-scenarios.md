# Runtime Routing Policy Scenarios

Use these scenarios to validate routing-policy behavior.

## Scenario 1: Allowed persona + OBO token

- Input persona: `manager`
- Target route: `sales_insights_agent` (`auth_mode=obo`)
- Forwarded token: present
- Expected result: route allowed and successful response.

## Scenario 2: Allowed persona + missing OBO token

- Input persona: `manager`
- Target route: `sales_insights_agent` (`auth_mode=obo`)
- Forwarded token: missing
- Expected result: clear authorization error, no silent fallback to `app`.

## Scenario 3: Disallowed persona

- Input persona: `guest`
- Target route: `sales_insights_agent`
- Expected result: policy deny before tool execution.

## Scenario 4: Evidence required output

- Input persona: `executive`
- Target route: `product_index_assistant`
- Expected result: response includes evidence/citation metadata or is blocked by guardrail.

## Scenario 5: Cross-route policy consistency

- Input persona: `analyst`
- Candidate routes: `product_index_assistant` and `sales_insights_agent`
- Expected result: only policy-allowed route is selected; blocked route is not invoked.
