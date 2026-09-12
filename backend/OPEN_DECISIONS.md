# OPEN DECISIONS

> **2026-09-12: every entry below now has a pragmatic test/demo decision
> in [`DECISIONS_TAKEN.md`](DECISIONS_TAKEN.md)**, taken at the Product
> Owner's explicit request so Sprint 1-5 testing is not blocked by them.
> This file keeps the original analysis (why each thing is genuinely
> ambiguous); `DECISIONS_TAKEN.md` records what was decided for testing —
> read both together. Real business-value decisions (OD-001 tariffs, the
> official OD-002 rounding/currency policy, the real relationship-code
> catalogue, the real Identity Provider) are still explicitly **not**
> resolved — the test decisions never claim to be real approved values.

- **S01-PERSISTENCE-001 — RESOLVED (2026-09-10):** PostgreSQL is mandatory in
  every environment, not optional. The foundation migration
  (`apps/foundation/infrastructure/migrations/0001_foundation_baseline.py`)
  ports `ART-012` V001-V003 verbatim (schemas, `jsonb`, `CHECK` constraints)
  and cannot run on SQLite. A SQLite fallback would let `migrate` "succeed"
  against a schema that silently diverges from ART-005/ART-012 — exactly
  what DOC-000 s3 P-08 ("Database migration only") forbids. Local dev uses
  `docker compose up db`; automated tests provision a disposable Postgres
  via Testcontainers unless `Q360_TEST_POSTGRES=true` points at an
  already-running instance (see `tests/conftest.py`).

- **S01-AUTH-001 — OPEN (OD-009, DOC-004 "Open Decisions"; DOC-001 "Identity
  Provider: autenticação/claims conforme ambiente"):** no approved Q360
  document fixes the concrete OIDC/Identity Provider or the exact JWT claim
  names for tenant/roles. `apps/foundation/infrastructure/jwt_actor_adapter.py`
  implements a standards-based OAuth2/OIDC Resource Server (JWKS signature
  validation, issuer/audience/expiry checks) that is configuration-driven
  rather than hardcoded to one vendor:
  - `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` — provider endpoints.
  - `OIDC_TENANT_CLAIM` (default `tenant_id`), `OIDC_ROLES_CLAIM` (default
    `roles`), `OIDC_SCOPE_CLAIM` (default `scope`, RFC 8693 standard name) —
    claim names, overridable per environment. Note: the OAuth2 *scope
    values* (`q360.read`/`write`/`approve`/`admin`/`audit`) are already
    fixed by ART-006 `components.securitySchemes.oauth2` — only the claim
    name carrying them is open, same as tenant/roles.
  - `OIDC_STATIC_VERIFICATION_KEY` — local/dev-only escape hatch when no IdP
    is running; `config/settings/production.py` refuses to start if it is
    set, and refuses to start if the three provider settings above are
    unset.
  **Action needed:** Product Owner / Tech Lead must name the actual IdP
  (e.g. Keycloak, Auth0, Azure AD B2C) and confirm the tenant/roles claim
  names before Sprint 3 (client/proponent data starts depending on a real
  authenticated tenant beyond foundation's own tests). Until then, do not
  hardcode a specific vendor's claim shape anywhere in the codebase —
  update the settings above instead.

- **S02-CONTRACT-001 — OPEN (found while implementing Q360-S2-02):** ART-006
  (the final HTTP authority, DOC-004 s2) has **zero** paths or schema fields
  for `Benefit`/`PlanBenefit`, even though ART-005 has the tables, ART-012
  V006 creates them, and DOC-004 s7 explicitly lists `Benefit` and
  `PlanBenefit` as Product module components. `PlanCreateRequest` has no
  `benefits` field either — a plan cannot be given any benefit through any
  documented endpoint today.
  `apps/product/infrastructure/models.py` has `Benefit`/`PlanBenefit`
  models (the tables must exist per ART-005/ART-012, and the future pricing
  engine will need to read `plan_benefit.configuration_json`), but
  deliberately **no** serializer, view or URL — adding one would be
  inventing an endpoint DOC-000's golden rule forbids.
  **Action needed:** Product Owner / Tech Lead must raise a Change Request
  against ART-006 to add Benefit management (its own CRUD, or fields on
  `PlanCreateRequest`/`Plan` — that shape choice is itself part of the CR)
  before Sprint 4/5 pricing work needs to read real benefit configuration,
  and before the frontend can build any benefit-management screen.

- **S02-PRODUCT-VERSION-OVERLAP — judgment call, not fully pinned by any
  document (documented here for transparency, not because it is
  "resolved"):** DOC-004 s7 states the invariant "vigências incompatíveis
  não se sobrepõem" but does not say whether the check runs at
  `POST .../versions` (create) or at `.../publish`, nor whether it should
  consider only PUBLISHED versions or every non-RETIRED one.
  `apps/product/application/product_service.create_product_version`
  enforces it at **create time**, against **every DRAFT+PUBLISHED** version
  of the same product — reasoned from `createProductVersion`'s ART-006
  responses including `400 BadRequest` (a real validation-failure path)
  while `publishProductVersion`'s `422 Unprocessable` has no S2 trigger
  defined for it yet. If Product/Actuarial decides overlap should instead
  be allowed between two DRAFT versions (only blocking at publish), this is
  a one-function change, not a schema change — flag it here rather than
  silently changing behaviour.
  Related: `ProductVersion.checksum` (ART-005/ART-006 field) is left `NULL`
  on publish — no approved document specifies what it should hash.

- **S03-RELATIONSHIP-001 — OPEN (found while implementing Q360-S3-02):**
  DOC-004 s8 claims the member "Relationship catalogue [is] finalized in
  ART-011" — it is not. ART-011's own "Code Catalogues" sheet (checked
  directly) has catalogues for tenant/product/rule/eligibility/quote/review/
  pricing-run/document/decision states, but **none** for relationship codes.
  `insured_member.relationship_code` (ART-005) is a free `varchar(40)` with
  no DB `CHECK`, and ART-006's `Member.relationshipCode` is an unconstrained
  `string`. Consequently, Q360-S3-02's acceptance criterion "Dependente
  requer titular" is **not implemented** — enforcing it would require
  hardcoding which literal string means "titular" (e.g. `"TITULAR"`), which
  is exactly the kind of invented business assumption DOC-000's golden rule
  forbids. `apps/client/application/member_service.py` only enforces "Datas
  coerentes" (dateOfBirth not in the future); "Relação válida" reduces to
  the structural ART-006 constraint already enforced by the serializer.
  **Action needed:** Product Owner must publish the relationship code
  catalogue (which strings exist, and which one denotes the policyholder)
  before this cross-member invariant can be implemented.

- **S03-IMPORT-001 — judgment calls, not pinned by any document (Q360-S3-04):**
  three implementation decisions with no authoritative source, documented
  for transparency:
  1. **File storage.** ART-005 `import_job` has no column for the
     uploaded file's bytes, only metadata (filename, checksum, row counts),
     and there is no staging table for parsed-but-uncommitted rows. The
     file is saved to Django's default file storage at a path derived from
     `(tenant_id, import_job.id, filename)` and re-read at commit time.
     Schema-neutral, but a storage architecture decision this repo is
     making unilaterally.
  2. **CSV column mapping.** No "import template" is defined anywhere. The
     expected header row reuses ART-006 `MemberCreateRequest`'s own field
     names verbatim (`relationshipCode,firstName,lastName,dateOfBirth,
     sexCode,externalReference`) — the least-invented mapping available.
     The free-form `attributes` object is not supported via CSV in V1.
  3. **`proposerId` required at commit despite being optional at upload.**
     ART-006's `uploadMemberImport` multipart body only requires `file`
     (`proposerId` is optional), but `insured_member.proposer_id` is
     `NOT NULL` (ART-005) — a job with no proposer structurally cannot
     produce members. `commit_member_import` raises `ImportCommitNotAllowedError`
     (409 CONFLICT) in that case.
  **Action needed:** none blocking — revisit if Product specifies an actual
  import template or async/queued processing (the current implementation is
  synchronous within the request, matching V1's "no messaging without a
  real consumer" principle, DOC-002 s4 Premissas).

- **S03-ELIGIBILITY-001 — judgment calls, not pinned by any document
  (Q360-S3-03):** ART-008's Rule Matrix fully specifies ELIG-001..ELIG-010
  (conditions, outcomes, codes), but several are `DRAFT` status with
  explicitly unresolved parameters (OD-004: "Threshold unresolved" / "No
  medical criteria invented in V1"). This repo implements the full
  ELIG-001..ELIG-010 pipeline (`apps/eligibility/domain/evaluation.py`) but:
  1. **No threshold is hardcoded.** `minEntryAge`/`maxEntryAge`/
     `allowedRelationshipCodes`/`referralCriteria`/`warningCriteria` are all
     read from a tenant's published `RuleVersion.artifact_ref`
     (rule_domain=ELIGIBILITY, `artifact_type=JSON`). An unconfigured
     threshold is a no-op (never fires), never an invented default.
  2. **`referralCriteria`/`warningCriteria` JSON shape (`Criterion` in
     domain/evaluation.py: optional `relationshipCodes`/`minAge`/`maxAge`,
     AND'd within an entry, OR'd across entries) is this repo's own minimal,
     generic placeholder** — ART-008 explicitly says "No medical criteria
     invented in V1" for ELIG-008, so no real criteria exist to copy. This
     makes the engine and API real and testable now; Actuarial/Product
     should define actual referral/warning criteria and this shape may need
     to change to accommodate them.
  3. **`createRuleVersion`/`publishConfiguration(rule-version)` were built
     now, not deferred to Sprint 5:** without them, no admin could ever
     publish an ELIGIBILITY rule_version, and evaluation could never
     produce anything but CONFIG_ERROR — Q360-S3-03's own acceptance
     criteria (demonstrating ELIGIBLE/WARNING/REFERRAL/HARD_STOP) would be
     unmeetable. Both endpoints are exactly as ART-006 defines them, not
     invented; only their *timing* (S3 instead of S5) is a judgment call.
  4. **A referenced `productVersionId`/`planId` that does not exist** maps
     to HTTP 400 `VALIDATION-400` (`ReferencedEntityNotFoundError`), not a
     persisted HARD_STOP evaluation — `eligibility_evaluation.product_version_id`/
     `plan_id` are `NOT NULL` (ART-005), so there is nothing to persist.
     `evaluateEligibility` has no 404 in its ART-006 response set, hence 400.
  **Action needed:** Product Owner/Actuarial to define real referral/warning
  criteria semantics before Sprint 7 (where REFERRAL feeds manual
  underwriting review) depends on this being more than a placeholder.

- **S04-ROUNDING-001 — OPEN (OD-002, ART-006 `x-q360-open-decisions`):** no
  approved document fixes the official currency/rounding policy. ART-013's
  only "official" pricing golden test (`golden/PENDING_OD_pricing_template.json`,
  caseId `GT-PRICE-OFFICIAL-001`) is itself `status: PENDING_OD`, blocked on
  OD-001/OD-002 — confirming this is genuinely unresolved, not an oversight.
  `apps/pricing/domain/money.py` implements an explicit, versioned,
  swappable placeholder (`OD-002-PLACEHOLDER-HALF-UP-2DP`, `ROUND_HALF_UP`
  to 2dp, applied at every component, not just the final total — so
  `PricingResponse.totalAmount` always reconciles exactly against the sum
  of visible components) instead of an implicit float truncation, satisfying
  Q360-S4-03's actual acceptance criteria ("rounding mode explícito", "total
  reconcilia") without pretending a business decision has been made. Every
  `PricingRun` records the policy code+version it used, so a future real
  policy never silently reinterprets a past run.
  **Action needed:** Product Owner/Actuarial must approve OD-001 (tariffs)
  and OD-002 (rounding) before any real (non-fixture) pricing output can be
  trusted; `BASE_PREMIUM`/`RatingFactor`/`PricingAdjustment` values used in
  tests are all fixture data (same posture as ART-013's GT-PRICE-005
  "technical fixture" golden test), never real Angolan tariffs.

- **S04-PRICING-CONTEXT-001 — judgment call, not pinned by any document
  (Q360-S4-02):** ART-006's `PricingCalculateRequest.context` is
  `additionalProperties: true` with no sub-fields fixed by any artifact, and
  neither `Plan` nor `ProductVersion` carries a field naming which
  `RatingTable`/`PricingParameterSet` applies to it — there is no other way
  to resolve them. `apps/pricing/application/pricing_engine.py` requires the
  caller to name them explicitly inside `context`: `ratingTableCode`
  (required), `parameterSetCode` (required), `ruleVersionCode` (optional,
  rule_domain=PRICING), `members: {<memberId>: {<dimension>: value}}`
  (optional, per-member factor-matching dimensions, e.g. `{"ageBand":
  "30-39"}`). Missing `ratingTableCode`/`parameterSetCode` is rejected as
  `VALIDATION-400` before any `PricingRun` row is created.
  Also **this module's own convention, not an invented business rule**: the
  rating chain is BASE (`PricingParameterSet` parameter code
  `BASE_PREMIUM`, DECIMAL) → each distinct `RatingFactor.factor_code` on the
  resolved `RatingTable`, applied multiplicatively in code order → optional
  PRICING `RuleVersion` adjustments (additive) — see S05-PRICING-RULES-001.
  **Action needed:** if/when ART-006 or DOC-003 defines a fixed way to
  associate a Plan with its RatingTable/PricingParameterSet, replace this
  `context`-based convention with that instead of maintaining both.

- **S04-CROSS-MODULE-001 — pre-existing pattern, extended, not newly
  introduced (Q360-S4-02):** DOC-004 s3 states "Não introduzir dependência
  entre módulos através de tabelas/repositórios internos de outro módulo;
  usar application ports/contracts" — strictly, this calls for a
  port/adapter per module boundary. `apps.eligibility.application.use_cases`
  already imports `apps.product.infrastructure.models` (`Plan`,
  `ProductVersion`) and `apps.client.infrastructure.models` (`InsuredMember`,
  `Proposer`) directly (Sprint 3, already shipped and audited). The pricing
  engine (`apps/pricing/application/pricing_engine.py`,
  `apps/pricing/infrastructure/models.py`) does the same for the same
  entities plus `apps.product.infrastructure.models.PricingParameterSet`,
  for consistency with the already-shipped pattern rather than introducing
  a second, inconsistent style (ports for pricing, direct imports for
  eligibility) without a broader refactor.
  **Action needed:** a future pass could introduce real
  `application/ports.py` contracts for these cross-module reads across both
  `eligibility` and `pricing` together — flagged as technical debt, not
  blocking any current story.

- **S05-PRICING-RULES-001 — judgment call, mirrors S03-ELIGIBILITY-001
  (Q360-S5-01):** no approved artifact defines what a "Drools rule" actually
  contains for pricing. DOC-003's S5-01 says "Drools integration + rule
  resolver", but ART-006's `RuleSetVersionRequest` only ever carries an
  opaque `artifactRef`/`artifactChecksum` pointer (`artifactType`: DRL /
  DECISION_TABLE / JSON / INTERNAL) — no artifact ships an executable rule
  DSL or its semantics. `apps/pricing/domain/pricing_rules.py`
  (`PricingRuleConfig`/`PricingAdjustment`) is this repo's own minimal,
  generic, additive-adjustment placeholder — same posture and same
  transparency as `EligibilityRuleConfig`/`Criterion`. A published PRICING
  RuleVersion's `artifact_ref` (artifact_type=JSON) is parsed as
  `{"adjustments": [{"code", "when": {dims}, "amount": "decimal-string"}]}`;
  an adjustment applies (additively) when its `when` dict is satisfied by
  the member's calculation context.
  **Action needed:** Product/Actuarial to define the real pricing rule
  semantics (and, separately, whether an actual Drools/DMN engine is even
  in scope for V1) before this placeholder is asked to carry real business
  logic.

- **S05-RULE-FOUR-EYES-001 — OPEN, structurally blocked (Q360-S5-01
  Security/Observability AC "Four-eyes para publicação"):** ART-012 V013
  already has `rule_version.approved_by` and a `CHECK
  (approved_by IS NULL OR published_by IS NULL OR approved_by <>
  published_by)` — the schema anticipates a maker-checker flow. However
  ART-006's `POST /api/v1/configuration/{configType}/{configId}/publish`
  (the only publish endpoint, shared by rating-table/pricing-parameter-set/
  rule-version) has **no request body at all** — no field exists anywhere
  in ART-006 to convey "who approved this" separately from "who is
  publishing this now", and no second endpoint (e.g. a distinct `/approve`
  step) exists either. `publish_rule_version`
  (`apps/foundation/application/rule_service.py`) therefore never populates
  `approved_by` (it stays `NULL`, which the CHECK permits) — implementing a
  real two-actor gate would mean inventing an undocumented request field or
  endpoint, which DOC-000's golden rule and DOC-004 s2 ("ART-006 é
  autoridade final do HTTP") both forbid.
  **Action needed:** Product Owner/Tech Lead must raise a Change Request
  against ART-006 (new field on the publish request, or a distinct approval
  endpoint) before four-eyes can be enforced for RuleVersion publication.

- **S04-LISTING-GAPS-001 — OPEN, found while wiring the frontend to the real
  backend (Q360 UI integration, 2026-09-12):** ART-006 has no
  `listProductVersions`/`getProductVersion` for `ProductVersion`, and no
  `listRatingTables`/`getRatingTable` or `listPricingParameterSets`/
  `getPricingParameterSet` for those two versioned config types either —
  only `POST` create and `POST .../publish` exist for all three. This means
  a `ProductVersion`/`RatingTable`/`PricingParameterSet` can only ever be
  obtained as the direct response of creating or publishing it; there is no
  way to browse what already exists.
  Consequences already visible in the frontend
  (`Q360-Linha-Sa-de-frontend/src/domains/product/hooks/useKnownVersions.ts`):
  the Products UI can only show versions the current browser itself
  created/published or manually registered by pasting an id — a page
  reload or a different browser/tester sees nothing, even though the data
  is real and published server-side. The Pricing UI likewise cannot offer
  a dropdown of existing RatingTable/PricingParameterSet codes — the
  operator must know/type `ratingTableCode`/`parameterSetCode` directly
  (see `Q360-Linha-Sa-de-frontend/src/domains/pricing/PricingPage.tsx`).
  **Action needed:** Product Owner/Tech Lead should raise a Change Request
  against ART-006 to add the missing list/get endpoints for these three
  resources — this is a pure read-side gap (no business value to invent),
  should be uncontroversial to approve, and would remove the local-cache
  workaround entirely once available.
