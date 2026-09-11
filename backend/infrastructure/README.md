# Infrastructure

Reserved for cross-module technical infrastructure that is not specific to
one bounded context — e.g. a shared RabbitMQ connection/outbox setup used by
several modules' own `infrastructure/` adapters (DOC-004 s3.1 `integration`
module, Sprint 9+). No RabbitMQ integration is included in S01.

Per-module persistence and adapter code (e.g. the foundation module's
`Tenant`/`AuditEvent` ORM models and JWT adapter) lives inside that module,
at `apps/<module>/infrastructure/`, not here — see DOC-004 s3 layering.
