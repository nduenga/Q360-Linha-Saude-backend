# Q360-MVP-ART-012 — Migrations V001–V026 V1

- Flyway only; PostgreSQL 15+.
- 26 forward-only migrations.
- Do not edit a migration after successful deployment to a shared environment.
- ART-011 DEV_TEST seed is deliberately excluded from V001–V026.
- V025 adds `q360.consumer_inbox` to close the ART-007 consumer-idempotency persistence gap.
- V026 installs cross-tenant/immutability guards and structural validation.
- No unresolved commercial value is introduced.

## Release validation
Run `flyway validate`, then `flyway migrate` on a clean PostgreSQL 15+ instance and execute the controls in the workbook Validation Plan. Confirm V001–V026 are successful in `flyway_schema_history` and checksums remain stable.

## Rollback policy
A migration failing inside its transaction should roll back. After a migration has successfully deployed, use a new forward corrective migration. Destructive production rollback requires an approved backup/restore procedure; do not improvise DOWN SQL.
