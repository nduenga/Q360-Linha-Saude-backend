"""Member population import orchestration (Q360-S3-04).

DESIGN NOTE — not fully pinned by any approved document, documented here
for transparency (see OPEN_DECISIONS.md#S03-IMPORT-001):
- ART-005's `import_job` has no column for the file's bytes (only
  metadata: filename, checksum, row counts) and there is no staging table
  for parsed-but-not-committed rows. The uploaded file is therefore saved
  to Django's file storage at a path derived from the ImportJob id, and
  re-read at commit time — schema-neutral, but a storage decision no
  document specifies.
- The expected file is CSV with a header row matching ART-006
  `MemberCreateRequest` field names exactly (`relationshipCode,firstName,
  lastName,dateOfBirth,sexCode,externalReference`) — the least-invented
  column mapping available, since no approved "import template" exists.
  The free-form `attributes` object is not supported via CSV in V1.
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass, field

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.client.domain.enums import ImportJobStatus, ImportType
from apps.client.domain.errors import ImportCommitNotAllowedError
from apps.client.infrastructure.models import ImportJob, ImportRowError, InsuredMember, Proposer

_audit = AuditService(DjangoAuditRepositoryAdapter())
_EXPECTED_COLUMNS = ["relationshipCode", "firstName", "lastName", "dateOfBirth", "sexCode", "externalReference"]


@dataclass
class _ParsedRow:
    row_number: int
    values: dict[str, str]
    errors: list[tuple[str | None, str, str]] = field(default_factory=list)  # (field, code, message)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _storage_path(tenant_id, import_job_id, filename: str) -> str:
    return f"member-imports/{tenant_id}/{import_job_id}/{filename}"


def _parse_date(raw: str) -> tuple[object | None, str | None]:
    if not raw:
        return None, None
    try:
        return timezone.datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"'{raw}' is not a valid YYYY-MM-DD date"


def _validate_row(row_number: int, raw: dict[str, str]) -> _ParsedRow:
    parsed = _ParsedRow(row_number=row_number, values=raw)
    relationship_code = (raw.get("relationshipCode") or "").strip()
    if not relationship_code or len(relationship_code) > 40:
        parsed.errors.append(("relationshipCode", "VALIDATION-400", "relationshipCode is required (max 40 chars)"))

    date_of_birth, date_error = _parse_date((raw.get("dateOfBirth") or "").strip())
    if date_error:
        parsed.errors.append(("dateOfBirth", "VALIDATION-400", date_error))
    elif date_of_birth is not None:
        try:
            if date_of_birth > timezone.now().date():
                parsed.errors.append(("dateOfBirth", "VALIDATION-400", "dateOfBirth is in the future"))
        except TypeError:  # pragma: no cover - defensive
            pass
    return parsed


def upload_member_import(*, proposer: Proposer | None, uploaded_file: UploadedFile, actor_id: str) -> ImportJob:
    tenant_id = CurrentTenantProvider.require()
    content = uploaded_file.read()
    checksum = hashlib.sha256(content).hexdigest()

    import_job = ImportJob.objects.create(
        tenant_id=tenant_id.value,
        proposer=proposer,
        import_type=ImportType.MEMBER_POPULATION.value,
        original_filename=uploaded_file.name,
        file_checksum=checksum,
        status=ImportJobStatus.VALIDATING.value,
        created_by=actor_id,
    )

    path = _storage_path(tenant_id.value, import_job.id, uploaded_file.name)
    default_storage.save(path, io.BytesIO(content))

    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = [_validate_row(i, raw) for i, raw in enumerate(reader, start=1)]
    except (UnicodeDecodeError, csv.Error):
        import_job.status = ImportJobStatus.FAILED.value
        import_job.completed_at = timezone.now()
        import_job.save(update_fields=["status", "completed_at"])
        _audit.record(action="member_import.failed", entity_type="ImportJob", entity_id=str(import_job.id))
        return import_job

    ImportRowError.objects.bulk_create(
        [
            ImportRowError(
                tenant_id=tenant_id.value,
                import_job=import_job,
                row_number=row.row_number,
                field_name=field_name,
                error_code=code,
                error_message=message,
            )
            for row in rows
            for field_name, code, message in row.errors
        ]
    )

    import_job.total_rows = len(rows)
    import_job.valid_rows = sum(1 for r in rows if r.is_valid)
    import_job.invalid_rows = import_job.total_rows - import_job.valid_rows
    import_job.status = ImportJobStatus.VALIDATED.value
    import_job.save(update_fields=["total_rows", "valid_rows", "invalid_rows", "status"])

    _audit.record(
        action="member_import.uploaded",
        entity_type="ImportJob",
        entity_id=str(import_job.id),
        metadata={"totalRows": import_job.total_rows, "validRows": import_job.valid_rows},
    )
    return import_job


def commit_member_import(*, import_job: ImportJob, actor_id: str) -> ImportJob:
    if import_job.status != ImportJobStatus.VALIDATED.value:
        raise ImportCommitNotAllowedError(
            f"ImportJob {import_job.id} is {import_job.status}; only a VALIDATED job can be committed"
        )
    if import_job.proposer_id is None:
        # ART-006 allows `proposerId` to be omitted on upload, but
        # `insured_member.proposer_id` is NOT NULL (ART-005) — a job
        # without a proposer structurally cannot be committed. Not
        # explicitly resolved by any document; documented in
        # OPEN_DECISIONS.md#S03-IMPORT-001.
        raise ImportCommitNotAllowedError(
            f"ImportJob {import_job.id} has no proposer; a proposer is required to commit members"
        )

    tenant_id = CurrentTenantProvider.require()
    path = _storage_path(tenant_id.value, import_job.id, import_job.original_filename)
    with default_storage.open(path) as fh:
        content = fh.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    rows = [_validate_row(i, raw) for i, raw in enumerate(reader, start=1)]

    import_job.status = ImportJobStatus.COMMITTING.value
    import_job.save(update_fields=["status"])

    created = 0
    with transaction.atomic():
        for row in rows:
            if not row.is_valid:
                continue
            date_of_birth, _ = _parse_date((row.values.get("dateOfBirth") or "").strip())
            InsuredMember.objects.create(
                tenant_id=tenant_id.value,
                proposer=import_job.proposer,
                relationship_code=row.values["relationshipCode"].strip(),
                first_name=(row.values.get("firstName") or "").strip() or None,
                last_name=(row.values.get("lastName") or "").strip() or None,
                date_of_birth=date_of_birth,
                sex_code=(row.values.get("sexCode") or "").strip() or None,
                external_reference=(row.values.get("externalReference") or "").strip() or None,
            )
            created += 1

        import_job.status = ImportJobStatus.COMPLETED.value
        import_job.completed_at = timezone.now()
        import_job.save(update_fields=["status", "completed_at"])

    _audit.record(
        action="member_import.committed",
        entity_type="ImportJob",
        entity_id=str(import_job.id),
        metadata={"membersCreated": created},
    )
    return import_job
