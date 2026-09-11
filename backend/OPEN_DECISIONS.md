# OPEN DECISIONS

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
