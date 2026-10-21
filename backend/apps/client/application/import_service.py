"""Member population import orchestration (Q360-S3-04).

DESIGN NOTE — not fully pinned by any approved document, documented here
for transparency (see OPEN_DECISIONS.md#S03-IMPORT-001):
- ART-005's `import_job` has no column for the file's bytes (only
  metadata: filename, checksum, row counts) and there is no staging table
  for parsed-but-not-committed rows. The uploaded file is therefore saved
  to Django's file storage at a path derived from the ImportJob id, and
  re-read at commit time — schema-neutral, but a storage decision no
  document specifies.
- The expected columns match ART-006 `MemberCreateRequest` field names
  exactly (`relationshipCode,firstName,lastName,dateOfBirth,sexCode,
  externalReference`) — the least-invented column mapping available,
  since no approved "import template" exists. The free-form `attributes`
  object is not supported via file import in V1.

Excel (`.xlsx`) is the only supported import format. A basic ETL pass now rejects an entire row (not
just missing/malformed dates) whenever any expected field contains a
literal null-looking placeholder (`null`, `n/a`, `nan`, `none`, `-`,
case-insensitive) instead of being left genuinely empty, and
`relationshipCode` is validated against the real catalogue (OD-003,
apps/client/application/relationship_service.py) at upload time, not only
at commit time.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.client.application.relationship_service import validate_relationship_code
from apps.client.application.member_service import _category_by_code, _person_label, max_beneficiaries_for_individual
from apps.client.domain.enums import ImportJobStatus, ImportType, MemberStatus, ProposerType, RelationshipCategory
from apps.client.domain.errors import (
    ImportCommitNotAllowedError,
    ImportPopulationInvalidError,
    UnknownRelationshipCodeError,
)
from apps.client.domain.rules import Person, validate_household
from apps.foundation.domain.problem import DomainProblem
from apps.client.infrastructure.models import ImportJob, ImportRowError, InsuredMember, Proposer

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()
_EXPECTED_COLUMNS = ["relationshipCode", "firstName", "lastName", "dateOfBirth", "sexCode", "externalReference"]
_XLSX_EXTENSIONS = (".xlsx",)
_HEADERS_PT = {
    "relação com o titular": "relationshipCode", "relacao com o titular": "relationshipCode",
    "relação": "relationshipCode", "relacao": "relationshipCode", "nome": "firstName",
    "apelido": "lastName", "data de nascimento": "dateOfBirth", "sexo": "sexCode",
    "referência externa": "externalReference", "referencia externa": "externalReference",
}
# Common ETL "looks like a null but isn't really empty" placeholders that
# spreadsheet exports/manual entry tend to leave behind - OD-004 asks that
# these be caught explicitly, not silently treated as valid text values.
_NULL_LOOKALIKES = {"null", "n/a", "na", "nan", "none", "-", "--"}


class ImportFileParseError(Exception):
    """Raised when the uploaded file cannot be parsed at all (corrupt
    workbook, undecodable CSV, unsupported extension)."""


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


def _rows_from_xlsx(content: bytes) -> list[dict[str, str]]:
    import openpyxl

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises several distinct exception types for a corrupt file
        raise ImportFileParseError(str(exc)) from exc

    sheet = workbook.worksheets[0]
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header = [str(cell).strip() if cell is not None else "" for cell in next(rows_iter)]
        header = [_HEADERS_PT.get(name.casefold(), name) for name in header]
    except StopIteration:
        return []

    rows: list[dict[str, str]] = []
    for raw_row in rows_iter:
        if all(cell is None or str(cell).strip() == "" for cell in raw_row):
            continue  # a fully blank spreadsheet row is not a data row
        values = {}
        for column_name, cell in zip(header, raw_row):
            if not column_name:
                continue
            if cell is None:
                values[column_name] = ""
            elif hasattr(cell, "isoformat"):  # datetime/date cell (Excel stores dates as real dates)
                values[column_name] = cell.isoformat()[:10]
            else:
                values[column_name] = str(cell).strip()
        rows.append(values)
    return rows


def _parse_uploaded_rows(*, filename: str, content: bytes) -> list[dict[str, str]]:
    """Accept only the published Excel template; Portuguese headers map to the
    canonical field names used by validation."""
    lowered = (filename or "").lower()
    if lowered.endswith(_XLSX_EXTENSIONS):
        return _rows_from_xlsx(content)
    raise ImportFileParseError("Formato não suportado. Carregue o modelo Excel .xlsx.")


def _parse_date(raw: str) -> tuple[object | None, str | None]:
    if not raw:
        return None, None
    try:
        return timezone.datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"'{raw}' is not a valid YYYY-MM-DD date"


def _validate_row(row_number: int, raw: dict[str, str], *, tenant_id) -> _ParsedRow:
    parsed = _ParsedRow(row_number=row_number, values=raw)

    # OD-004 ETL pass: a null-lookalike placeholder in ANY expected column
    # is always a data error, regardless of which column it is in — a
    # spreadsheet cell reading "N/A" is never a valid firstName/sexCode/etc.
    for column in _EXPECTED_COLUMNS:
        value = (raw.get(column) or "").strip()
        if value.lower() in _NULL_LOOKALIKES:
            parsed.errors.append(
                (column, "VALIDATION-400", f"{column} contains '{value}', which looks like a placeholder for empty — leave the cell blank instead")
            )

    relationship_code = (raw.get("relationshipCode") or "").strip()
    if not relationship_code or len(relationship_code) > 40:
        parsed.errors.append(("relationshipCode", "VALIDATION-400", "relationshipCode is required (max 40 chars)"))
    elif relationship_code.lower() not in _NULL_LOOKALIKES:
        try:
            validate_relationship_code(tenant_id=tenant_id, code=relationship_code)
        except UnknownRelationshipCodeError:
            parsed.errors.append(
                ("relationshipCode", "VALIDATION-400", f"'{relationship_code}' is not a valid relationshipCode")
            )

    raw_dob = (raw.get("dateOfBirth") or "").strip()
    if not raw_dob:
        # Regra de negócio: data de nascimento obrigatória para toda a pessoa segura.
        parsed.errors.append(("dateOfBirth", "VALIDATION-400", "dateOfBirth is required"))
    date_of_birth, date_error = _parse_date(raw_dob)
    if date_error:
        parsed.errors.append(("dateOfBirth", "VALIDATION-400", date_error))
    elif date_of_birth is not None:
        try:
            if date_of_birth > timezone.now().date():
                parsed.errors.append(("dateOfBirth", "VALIDATION-400", "dateOfBirth is in the future"))
        except TypeError:  # pragma: no cover - defensive
            pass
    return parsed


def _population_problem(*, proposer: Proposer | None, rows: list[_ParsedRow]) -> str | None:
    """Aplica titular-primeiro, limite de beneficiários e diferença de 13
    anos ao conjunto FINAL (membros ativos já existentes + linhas válidas do
    ficheiro). Devolve a mensagem do problema, ou None se estiver tudo bem."""
    if proposer is None:
        return None
    categories = _category_by_code()
    people = [
        Person(
            categories.get(m.relationship_code, RelationshipCategory.OTHER.value),
            m.date_of_birth,
            _person_label(m.first_name, m.last_name),
        )
        for m in InsuredMember.objects.filter(proposer=proposer, status=MemberStatus.ACTIVE.value)
    ]
    for row in rows:
        if not row.is_valid:
            continue
        dob, _ = _parse_date((row.values.get("dateOfBirth") or "").strip())
        people.append(
            Person(
                categories.get(row.values["relationshipCode"].strip(), RelationshipCategory.OTHER.value),
                dob,
                _person_label((row.values.get("firstName") or "").strip(), (row.values.get("lastName") or "").strip()),
            )
        )
    individual = proposer.proposer_type == ProposerType.INDIVIDUAL.value
    try:
        validate_household(
            people, individual=individual, max_beneficiaries=max_beneficiaries_for_individual() if individual else None
        )
    except DomainProblem as exc:
        return str(exc)
    return None


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
        raw_rows = _parse_uploaded_rows(filename=uploaded_file.name, content=content)
        rows = [_validate_row(i, raw, tenant_id=tenant_id.value) for i, raw in enumerate(raw_rows, start=1)]
    except ImportFileParseError as exc:
        import_job.status = ImportJobStatus.FAILED.value
        import_job.completed_at = timezone.now()
        import_job.save(update_fields=["status", "completed_at"])
        _audit.record(
            action="member_import.failed",
            entity_type="ImportJob",
            entity_id=str(import_job.id),
            metadata={"result": "FAILURE", "reason": f"File decode or parsing error: {exc}"},
        )
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
    population_problem = _population_problem(proposer=proposer, rows=rows)
    if population_problem:
        # Erro ao nível do ficheiro (linha 0): o commit volta a validar e recusa.
        ImportRowError.objects.create(
            tenant_id=tenant_id.value,
            import_job=import_job,
            row_number=0,
            field_name="relationshipCode",
            error_code="VALIDATION-400",
            error_message=population_problem,
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
            f"O processo de importação {import_job.id} está em {import_job.status}; só um processo VALIDATED pode ser confirmado"
        )
    if import_job.proposer_id is None:
        # ART-006 allows `proposerId` to be omitted on upload, but
        # `insured_member.proposer_id` is NOT NULL (ART-005) — a job
        # without a proposer structurally cannot be committed. Not
        # explicitly resolved by any document; documented in
        # OPEN_DECISIONS.md#S03-IMPORT-001.
        raise ImportCommitNotAllowedError(
            f"O processo de importação {import_job.id} não tem cliente (proposer); é necessário um para confirmar as pessoas seguras"
        )

    tenant_id = CurrentTenantProvider.require()
    path = _storage_path(tenant_id.value, import_job.id, import_job.original_filename)
    with default_storage.open(path) as fh:
        content = fh.read()
    raw_rows = _parse_uploaded_rows(filename=import_job.original_filename, content=content)
    rows = [_validate_row(i, raw, tenant_id=tenant_id.value) for i, raw in enumerate(raw_rows, start=1)]

    population_problem = _population_problem(proposer=import_job.proposer, rows=rows)
    if population_problem:
        # Nada foi criado: o processo continua VALIDATED para o utilizador corrigir o ficheiro.
        raise ImportPopulationInvalidError(population_problem)

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
    _outbox.append(
        aggregate_type="ImportJob",
        aggregate_id=str(import_job.id),
        event_type="MEMBER.IMPORT.COMPLETED",
        payload={
            "importJobId": str(import_job.id),
            "proposerId": str(import_job.proposer_id) if import_job.proposer_id else None,
            "membersCreated": created,
            "totalRows": import_job.total_rows,
            "completedAt": import_job.completed_at.isoformat() if import_job.completed_at else None,
        },
    )
    return import_job
