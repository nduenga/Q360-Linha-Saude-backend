# Q360-MVP-ART-013 — Golden Tests V1

## Core invariant
Same normalized input + same exact versions + same rules + same rounding policy = exact same result.

## Active vs PENDING_OD
ACTIVE cases can be implemented now without inventing unresolved commercial policy.
PENDING_OD cases are deliberately incomplete templates until the referenced Open Decision is approved.

## Golden baseline change rule
A failing golden test is not fixed by blindly updating the expected file. A baseline change must be explained by an approved change in input semantics, product version, rating table, parameter set, rule version, rounding policy, or an explicitly approved defect correction.

## Exact decimal handling
Monetary and factor outputs are compared as canonical decimal strings / BigDecimal semantics, never binary float.

## Synthetic data
All examples are synthetic and must remain non-production.
