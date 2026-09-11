# Shared

Reserved for technical primitives that are genuinely cross-module and not
owned by any single bounded context (DOC-004 s3.1) — e.g. base
exceptions/DTO mixins used by more than one business module.

Authentication, tenancy and audit are **not** here: they belong to the
`foundation` module (`apps/foundation/`), which is the "shared kernel" named
in DOC-004 s6. Nothing has been added to this package yet — do not add
cross-cutting code here until a second business module beyond `foundation`
actually needs to share it.
