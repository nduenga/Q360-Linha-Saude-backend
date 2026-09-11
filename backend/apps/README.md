# Apps

Business Django apps, one per DOC-004 s3.1 module (foundation, product,
client, eligibility, pricing, quotation, underwriting, documents,
integration). Each app follows the same internal layering
(`domain/application/infrastructure/interfaces`) described in DOC-004 s3.

- `foundation` (Sprint 1) — tenant identity, JWT actor resolution, audit
  trail, correlation-id propagation. No business module may depend on
  another business module directly; only on `foundation`'s application
  ports. Also owns `RuleSet`/`RuleVersion` (ART-012 V012/V013) and their
  `/api/v1/rule-versions` endpoint — see the module docstring in
  `infrastructure/models.py` for why this cross-cutting "Rules" capability
  lives here rather than under `pricing`.
- `product` (Sprint 2) — Product, ProductVersion, Plan, versioned
  PricingParameterSet/PricingParameter. `Benefit`/`PlanBenefit` have models
  (ART-005/ART-012 require the tables) but no HTTP surface — ART-006 does
  not define one yet, see `OPEN_DECISIONS.md#S02-CONTRACT-001`.
- `client` (Sprint 3) — Proposer, InsuredMember, ImportJob/ImportRowError
  (member population CSV import).
- `eligibility` (Sprint 3) — EligibilityEvaluation; pure decision logic in
  `domain/evaluation.py` driven entirely by ART-008's Rule Matrix
  (ELIG-001..ELIG-010), configured via a published `foundation.RuleVersion`
  (rule_domain=ELIGIBILITY) — no threshold/criteria is hardcoded, see
  `OPEN_DECISIONS.md#S03-ELIGIBILITY-001`.

Further modules are added as their roadmap Sprint is reached (see
`docs/02-roadmap/`).
