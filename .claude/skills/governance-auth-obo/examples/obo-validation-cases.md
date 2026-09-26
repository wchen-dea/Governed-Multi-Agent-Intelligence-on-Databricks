# OBO Validation Cases

## Case 1: OBO with token

- Route `auth_mode=obo`
- Forwarded token present
- Expected: success

## Case 2: OBO without token

- Route `auth_mode=obo`
- Forwarded token absent
- Expected: explicit authorization error

## Case 3: APP route without token

- Route `auth_mode=app`
- Forwarded token absent
- Expected: success using app identity
