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

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.client.application.relationship_service import validate_relationship_code
from apps.client.application import household_service, member_service
from apps.client.application.member_service import _category_by_code, _person_label, max_beneficiaries_for_individual
from apps.client.domain.enums import ImportJobStatus, ImportType, MemberStatus, ProposerType, RelationshipCategory
from apps.client.domain.errors import (
    ImportCommitNotAllowedError,
    ImportPopulationInvalidError,
    UnknownRelationshipCodeError,
)
from apps.client.domain.rules import Person, validate_corporate_family, validate_household
from apps.foundation.domain.problem import DomainProblem
from apps.client.infrastructure.models import ImportJob, ImportRowError, InsuredMember, Person as PersonRecord, Proposer

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()
_EXPECTED_COLUMNS = [
    "relationshipCode", "firstName", "lastName", "dateOfBirth", "sexCode",
    "externalReference", "email", "phone",
]
_XLSX_EXTENSIONS = (".xlsx",)
_HEADERS_PT = {
    "relação com o titular": "relationshipCode", "relacao com o titular": "relationshipCode",
    "relação": "relationshipCode", "relacao": "relationshipCode", "nome": "firstName",
    "apelido": "lastName", "data de nascimento": "dateOfBirth", "sexo": "sexCode",
    "referência externa": "externalReference", "referencia externa": "externalReference",
    "tipo de pessoa": "memberType",
    "referência do colaborador titular": "holderReference",
    "referencia do colaborador titular": "holderReference",
    "e-mail": "email", "email": "email",
    "telefone": "phone",
}
# Common ETL "looks like a null but isn't really empty" placeholders that
# spreadsheet exports/manual entry tend to leave behind - OD-004 asks that
# these be caught explicitly, not silently treated as valid text values.
DUPLICATE_ROW_CODE = "IMPORT-DUPLICATE"
_NULL_LOOKALIKES = {"null", "n/a", "na", "nan", "none", "-", "--"}


class ImportFileParseError(Exception):
    """Raised when the uploaded file cannot be parsed at all (corrupt
    workbook, undecodable CSV, unsupported extension)."""


@dataclass
class _ParsedRow:
    row_number: int
    values: dict[str, str]
    errors: list[tuple[str | None, str, str]] = field(default_factory=list)  # (field, code, message)

    duplicate: bool = False

    @property
    def is_valid(self) -> bool:
        return not self.errors and not self.duplicate


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


def _person_key(first_name: str | None, last_name: str | None, date_of_birth) -> tuple:
    return (
        " ".join((first_name or "").split()).casefold(),
        " ".join((last_name or "").split()).casefold(),
        date_of_birth,
    )


def _mark_duplicates(*, proposer: Proposer | None, rows: list[_ParsedRow]) -> None:
    """Pessoas já existentes (referência, ou nome e data de nascimento) e linhas
    repetidas no ficheiro não entram de novo; ficam só assinaladas."""
    references: set[str] = set()
    people: set[tuple] = set()
    if proposer is not None:
        for member in InsuredMember.objects.filter(proposer=proposer):
            if member.external_reference:
                references.add(member.external_reference.strip().casefold())
            people.add(_person_key(member.first_name, member.last_name, member.date_of_birth))
    for row in rows:
        if not row.is_valid:
            continue
        reference = (row.values.get("externalReference") or "").strip().casefold()
        date_of_birth, _ = _parse_date((row.values.get("dateOfBirth") or "").strip())
        person = _person_key(row.values.get("firstName"), row.values.get("lastName"), date_of_birth)
        if (reference and reference in references) or person in people:
            row.duplicate = True
            continue
        if reference:
            references.add(reference)
        people.add(person)


def _rows_to_deduplicate(rows: list[_ParsedRow], *, household_import: bool) -> list[_ParsedRow]:
    """No modelo de colaboradores, uma referência repetida já é erro da linha;
    falta impedir que voltar a carregar o ficheiro duplique os dependentes."""
    if not household_import:
        return rows
    return [row for row in rows if row.values.get("memberType") == "DEPENDENTE"]


def _parse_date(raw: str) -> tuple[object | None, str | None]:
    if not raw:
        return None, None
    try:
        return timezone.datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"«{raw}» não é uma data válida; use o formato AAAA-MM-DD."


def _validate_row(row_number: int, raw: dict[str, str], *, tenant_id) -> _ParsedRow:
    parsed = _ParsedRow(row_number=row_number, values=raw)

    # OD-004 ETL pass: a null-lookalike placeholder in ANY expected column
    # is always a data error, regardless of which column it is in — a
    # spreadsheet cell reading "N/A" is never a valid firstName/sexCode/etc.
    for column in _EXPECTED_COLUMNS:
        value = (raw.get(column) or "").strip()
        if value.lower() in _NULL_LOOKALIKES:
            parsed.errors.append(
                (column, "VALIDATION-400", f"A coluna {column} contém «{value}»; deixe a célula vazia se não tiver este dado.")
            )

    relationship_code = (raw.get("relationshipCode") or "").strip()
    if not relationship_code or len(relationship_code) > 40:
        parsed.errors.append(("relationshipCode", "VALIDATION-400", "Indique a relação com o titular (até 40 caracteres)."))
    elif relationship_code.lower() not in _NULL_LOOKALIKES:
        try:
            validate_relationship_code(tenant_id=tenant_id, code=relationship_code)
        except UnknownRelationshipCodeError:
            parsed.errors.append(
                ("relationshipCode", "VALIDATION-400", f"«{relationship_code}» não é uma relação válida.")
            )

    raw_dob = (raw.get("dateOfBirth") or "").strip()
    if not (raw.get("firstName") or "").strip():
        parsed.errors.append(("firstName", "VALIDATION-400", "Indique o nome próprio da pessoa."))
    if not raw_dob:
        # Regra de negócio: data de nascimento obrigatória para toda a pessoa segura.
        parsed.errors.append(("dateOfBirth", "VALIDATION-400", "Indique a data de nascimento."))
    date_of_birth, date_error = _parse_date(raw_dob)
    if date_error:
        parsed.errors.append(("dateOfBirth", "VALIDATION-400", date_error))
    elif date_of_birth is not None:
        try:
            if date_of_birth > timezone.now().date():
                parsed.errors.append(("dateOfBirth", "VALIDATION-400", "A data de nascimento não pode estar no futuro."))
        except TypeError:  # pragma: no cover - defensive
            pass
    return parsed


def _is_organisation_household_import(rows: list[dict[str, str]]) -> bool:
    return bool(rows and any("memberType" in row for row in rows))


def _validate_organisation_household_rows(
    *, proposer: Proposer | None, rows: list[_ParsedRow], tenant_id,
) -> str | None:
    """Validate collaborator anchors and optional dependent groups in a flat workbook."""
    first_problem = None

    def add_error(row: _ParsedRow, field: str, message: str) -> None:
        nonlocal first_problem
        row.errors.append((field, "VALIDATION-400", message))
        first_problem = first_problem or f"Linha {row.row_number}: {message}"

    if proposer is None or proposer.proposer_type != ProposerType.ORGANISATION.value:
        message = "Este modelo só pode ser importado para um proponente do tipo organização."
        for row in rows:
            add_error(row, "memberType", message)
        return first_problem

    categories = _category_by_code()
    existing_members = {
        (member.external_reference or ""): member
        for member in InsuredMember.objects.filter(proposer=proposer)
        if member.external_reference
    }
    new_holders: dict[str, _ParsedRow] = {}
    seen_references: set[str] = set()
    existing_titular = InsuredMember.objects.filter(
        proposer=proposer,
        relationship_code="TITULAR",
        status=MemberStatus.ACTIVE.value,
    ).exists()
    seen_titular = False

    for row in rows:
        kind = (row.values.get("memberType") or "").strip().upper()
        row.values["memberType"] = kind
        code = (row.values.get("relationshipCode") or "").strip().upper()
        row.values["relationshipCode"] = code
        reference = (row.values.get("externalReference") or "").strip()
        holder_reference = (row.values.get("holderReference") or "").strip()

        if kind not in {"TITULAR", "COLABORADOR", "DEPENDENTE"}:
            add_error(row, "memberType", "Indique TITULAR, COLABORADOR ou DEPENDENTE.")
            continue

        if kind == "TITULAR":
            if categories.get(code) != RelationshipCategory.TITULAR.value:
                add_error(row, "relationshipCode", "Na linha de titular, a relação tem de ser TITULAR.")
            if holder_reference:
                add_error(row, "holderReference", "Deixe esta coluna vazia na linha do titular do proponente.")
            if existing_titular or seen_titular:
                add_error(row, "memberType", "A organização já tem um titular ativo. Retire esta linha do ficheiro: só pode existir um titular por organização.")
            seen_titular = True
            email = (row.values.get("email") or "").strip()
            phone = (row.values.get("phone") or "").strip()
            if not email:
                add_error(row, "email", "O e-mail do titular é obrigatório.")
            else:
                try:
                    validate_email(email)
                except ValidationError:
                    add_error(row, "email", "Indique um e-mail válido para o titular.")
                if proposer.email and email.casefold() == proposer.email.strip().casefold():
                    add_error(row, "email", "O e-mail do titular deve ser diferente do e-mail de contacto da organização.")
            if not phone:
                add_error(row, "phone", "O telefone do titular é obrigatório.")
            continue

        if kind == "COLABORADOR":
            if code and categories.get(code) != RelationshipCategory.COLLABORATOR.value:
                add_error(row, "relationshipCode", "Na linha de colaborador, a relação tem de ser COLABORADOR.")
            row.values["relationshipCode"] = "COLABORADOR"
            if holder_reference:
                add_error(row, "holderReference", "Deixe esta coluna vazia na linha do colaborador.")
            if not reference:
                add_error(row, "externalReference", "A referência externa do colaborador é obrigatória.")
            elif reference in seen_references:
                add_error(row, "externalReference", f"A referência '{reference}' está repetida no ficheiro.")
            elif reference in existing_members:
                add_error(row, "externalReference", f"A referência '{reference}' já existe nesta organização.")
            elif row.is_valid:
                seen_references.add(reference)
                new_holders[reference] = row
            continue

        if not holder_reference:
            add_error(row, "holderReference", "Indique a referência do colaborador titular do agregado.")
        if not code or categories.get(code) in (
            RelationshipCategory.COLLABORATOR.value, RelationshipCategory.TITULAR.value,
        ):
            add_error(row, "relationshipCode", "Indique uma relação familiar válida para o dependente.")
        if row.is_valid:
            try:
                validate_relationship_code(tenant_id=tenant_id, code=code)
            except UnknownRelationshipCodeError:
                add_error(row, "relationshipCode", f"'{code}' não é uma relação familiar válida neste tenant.")

    for row in rows:
        if not row.is_valid or row.values.get("memberType") != "DEPENDENTE":
            continue
        holder_reference = (row.values.get("holderReference") or "").strip()
        holder_row = new_holders.get(holder_reference)
        if holder_row is not None:
            holder_dob, _ = _parse_date((holder_row.values.get("dateOfBirth") or "").strip())
            holder_name = (holder_row.values.get("firstName") or "").strip()
        else:
            existing = existing_members.get(holder_reference)
            if (
                existing is None
                or existing.status != MemberStatus.ACTIVE.value
                or categories.get(existing.relationship_code) != RelationshipCategory.COLLABORATOR.value
            ):
                add_error(row, "holderReference", f"Não foi encontrado colaborador com a referência '{holder_reference}'.")
                continue
            holder_dob = existing.date_of_birth
            holder_name = _person_label(existing.first_name, existing.last_name)

        if not row.is_valid:
            continue
        dependent_dob, _ = _parse_date((row.values.get("dateOfBirth") or "").strip())
        relationship = categories.get(row.values["relationshipCode"], RelationshipCategory.OTHER.value)
        try:
            validate_corporate_family(
                employee=Person(RelationshipCategory.COLLABORATOR.value, holder_dob, holder_name),
                relatives=[Person(
                    relationship,
                    dependent_dob,
                    _person_label(row.values.get("firstName"), row.values.get("lastName")),
                )],
            )
        except DomainProblem as exc:
            add_error(row, "dateOfBirth", str(exc))

    return first_problem


def _population_problem(*, proposer: Proposer | None, rows: list[_ParsedRow]) -> str | None:
    """Aplica titular-primeiro, limite de beneficiários e diferença de 13
    anos ao conjunto FINAL (membros ativos já existentes + linhas válidas do
    ficheiro). Devolve a mensagem do problema, ou None se estiver tudo bem."""
    if proposer is None:
        return None
    if any(row.values.get("memberType") for row in rows):
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
    if not individual:
        for row in rows:
            if row.is_valid and categories.get(row.values["relationshipCode"].strip()) != RelationshipCategory.COLLABORATOR.value:
                return "A importação de uma organização só aceita COLABORADOR; familiares devem ser associados a um agregado familiar."
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

    organisation_household_import = _is_organisation_household_import(raw_rows)
    if organisation_household_import:
        _validate_organisation_household_rows(proposer=proposer, rows=rows, tenant_id=tenant_id.value)

    if (
        proposer is not None
        and proposer.proposer_type != ProposerType.INDIVIDUAL.value
        and not organisation_household_import
    ):
        # Numa organização cada linha é um colaborador: uma relação familiar é
        # um erro dessa linha (com o número dela), não do ficheiro inteiro.
        categories = _category_by_code()
        for row in rows:
            code = (row.values.get("relationshipCode") or "").strip()
            if row.is_valid and categories.get(code) != RelationshipCategory.COLLABORATOR.value:
                row.errors.append((
                    "relationshipCode", "VALIDATION-400",
                    "Numa organização cada pessoa importada é um colaborador (COLABORADOR); "
                    "os familiares associam-se depois ao agregado do colaborador.",
                ))

    _mark_duplicates(
        proposer=proposer, rows=_rows_to_deduplicate(rows, household_import=organisation_household_import),
    )

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
        + [
            ImportRowError(
                tenant_id=tenant_id.value,
                import_job=import_job,
                row_number=row.row_number,
                field_name=None,
                error_code=DUPLICATE_ROW_CODE,
                error_message="Esta pessoa já existe; a linha é ignorada.",
            )
            for row in rows
            if row.duplicate
        ]
    )
    population_problem = _population_problem(proposer=proposer, rows=rows)
    if population_problem:
        # Erro do conjunto (não de uma linha): fica na primeira linha de dados,
        # porque a tabela só aceita números de linha > 0; o commit volta a validar e recusa.
        ImportRowError.objects.create(
            tenant_id=tenant_id.value,
            import_job=import_job,
            row_number=min((r.row_number for r in rows), default=2),
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


def row_problems(import_job: ImportJob) -> list[dict]:
    """Erros e duplicados por linha. `sheetRow` é a linha que se vê no Excel: o
    cabeçalho ocupa a primeira."""
    return [
        {
            "rowNumber": row.row_number,
            "sheetRow": row.row_number + 1,
            "field": row.field_name,
            "code": row.error_code,
            "message": row.error_message,
            "duplicate": row.error_code == DUPLICATE_ROW_CODE,
        }
        for row in import_job.row_errors.order_by("row_number", "field_name")
    ]


def error_report(import_job: ImportJob) -> bytes:
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Erros"
    sheet.append(["Linha", "Campo", "Tipo", "Mensagem"])
    for problem in row_problems(import_job):
        sheet.append([
            problem["sheetRow"], problem["field"] or "", "Duplicado" if problem["duplicate"] else "Erro", problem["message"],
        ])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


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
    proposer = import_job.proposer
    if proposer is None:
        raise ImportCommitNotAllowedError(
            f"O processo de importação {import_job.id} não conseguiu carregar o cliente necessário para confirmar as pessoas seguras"
        )

    tenant_id = CurrentTenantProvider.require()
    path = _storage_path(tenant_id.value, import_job.id, import_job.original_filename)
    with default_storage.open(path) as fh:
        content = fh.read()
    raw_rows = _parse_uploaded_rows(filename=import_job.original_filename, content=content)
    rows = [_validate_row(i, raw, tenant_id=tenant_id.value) for i, raw in enumerate(raw_rows, start=1)]

    organisation_household_import = _is_organisation_household_import(raw_rows)
    if organisation_household_import:
        # Tal como no modelo simples, as linhas com erro ficam de fora e as
        # válidas entram; um dependente de um titular com erro também fica de fora.
        _validate_organisation_household_rows(proposer=import_job.proposer, rows=rows, tenant_id=tenant_id.value)

    _mark_duplicates(
        proposer=import_job.proposer, rows=_rows_to_deduplicate(rows, household_import=organisation_household_import),
    )
    if not any(row.is_valid for row in rows):
        raise ImportPopulationInvalidError("Não há linhas válidas para importar. Corrija o ficheiro e carregue-o de novo.")

    population_problem = _population_problem(proposer=import_job.proposer, rows=rows)
    if population_problem:
        # Nada foi criado: o processo continua VALIDATED para o utilizador corrigir o ficheiro.
        raise ImportPopulationInvalidError(population_problem)

    import_job.status = ImportJobStatus.COMMITTING.value
    import_job.save(update_fields=["status"])

    created = 0
    titular_email = None
    with transaction.atomic():
        if organisation_household_import:
            holders = {
                (member.external_reference or ""): member
                for member in InsuredMember.objects.filter(proposer=import_job.proposer, status=MemberStatus.ACTIVE.value)
                if member.external_reference
            }
            households = {}
            for row in rows:
                if not row.is_valid or row.values.get("memberType") != "TITULAR":
                    continue
                date_of_birth, _ = _parse_date(row.values["dateOfBirth"].strip())
                member_service.create_member(
                    proposer=import_job.proposer,
                    relationship_code="TITULAR",
                    first_name=row.values["firstName"].strip(),
                    last_name=(row.values.get("lastName") or "").strip() or None,
                    date_of_birth=date_of_birth,
                    sex_code=(row.values.get("sexCode") or "").strip() or None,
                    external_reference=(row.values.get("externalReference") or "").strip() or None,
                    attributes={
                        "email": row.values["email"].strip(),
                        "phone": row.values["phone"].strip(),
                    },
                    allow_organisation_titular=True,
                )
                titular_email = row.values["email"].strip()
                created += 1

            for row in rows:
                if not row.is_valid or row.values.get("memberType") != "COLABORADOR":
                    continue
                reference = row.values["externalReference"].strip()
                date_of_birth, _ = _parse_date(row.values["dateOfBirth"].strip())
                holders[reference] = member_service.create_member(
                    proposer=import_job.proposer,
                    relationship_code="COLABORADOR",
                    first_name=row.values["firstName"].strip(),
                    last_name=(row.values.get("lastName") or "").strip() or None,
                    date_of_birth=date_of_birth,
                    sex_code=(row.values.get("sexCode") or "").strip() or None,
                    external_reference=reference,
                    attributes=None,
                )
                created += 1

            for row in rows:
                if not row.is_valid or row.values.get("memberType") != "DEPENDENTE":
                    continue
                holder_reference = row.values["holderReference"].strip()
                holder = holders[holder_reference]
                household = households.get(holder_reference)
                if household is None:
                    household = holder.primary_household.filter(status="ACTIVE").first()
                    if household is None:
                        household = household_service.create_household(
                            proposer=import_job.proposer,
                            primary_member=holder,
                            joined_at=timezone.now().date(),
                        )
                    households[holder_reference] = household
                date_of_birth, _ = _parse_date(row.values["dateOfBirth"].strip())
                household_service.create_dependent(
                    household=household,
                    relationship_code=row.values["relationshipCode"].strip(),
                    first_name=row.values["firstName"].strip(),
                    last_name=(row.values.get("lastName") or "").strip() or None,
                    date_of_birth=date_of_birth,
                    sex_code=(row.values.get("sexCode") or "").strip() or None,
                    external_reference=(row.values.get("externalReference") or "").strip() or None,
                    attributes=None,
                    nif=None,
                    joined_at=timezone.now().date(),
                )
                created += 1
        else:
            for row in rows:
                if not row.is_valid:
                    continue
                date_of_birth, _ = _parse_date((row.values.get("dateOfBirth") or "").strip())
                first_name = (row.values.get("firstName") or "").strip() or None
                last_name = (row.values.get("lastName") or "").strip() or None
                sex_code = (row.values.get("sexCode") or "").strip() or None
                person_record = PersonRecord.objects.create(
                    tenant_id=tenant_id.value,
                    first_name=first_name or "Pessoa",
                    last_name=last_name,
                    date_of_birth=date_of_birth,
                    sex_code=sex_code,
                )
                InsuredMember.objects.create(
                    tenant_id=tenant_id.value,
                    proposer=import_job.proposer,
                    person=person_record,
                    relationship_code=row.values["relationshipCode"].strip(),
                    first_name=first_name,
                    last_name=last_name,
                    date_of_birth=date_of_birth,
                    sex_code=sex_code,
                    external_reference=(row.values.get("externalReference") or "").strip() or None,
                )
                created += 1

        import_job.status = ImportJobStatus.COMPLETED.value
        import_job.completed_at = timezone.now()
        import_job.save(update_fields=["status", "completed_at"])

    if titular_email:
        from apps.customer_portal.application.invitation_service import invite_proposer

        invite_proposer(proposer, recipient_email=titular_email)

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
