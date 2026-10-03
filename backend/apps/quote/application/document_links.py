"""URLs assinadas e com expiração para descarregar documentos.

`POST /documents/{id}/signed-url` (autenticado) devolve uma ligação que
qualquer pessoa com ela pode abrir até expirar, sem iniciar sessão (ex.:
enviar a proposta ao cliente). O token é assinado (HMAC, `SECRET_KEY`), liga
o documento ao inquilino e traz a hora de expiração; o prazo vem do
parâmetro de sistema `documents.signed_url_ttl_seconds`. Cada abertura fica
auditada e o ficheiro continua a passar a verificação de checksum.
"""
from __future__ import annotations

import datetime
import uuid

from django.core import signing
from django.utils import timezone

from apps.foundation.application import system_parameter_service
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.quote.application import proposal_service

_SALT = "q360.document-link.v1"
_audit = AuditService(DjangoAuditRepositoryAdapter())
TTL_PARAMETER = "documents.signed_url_ttl_seconds"


class InvalidDocumentLinkError(DomainProblem):
    http_status = 403
    problem_code = "SEC-403"


def create_link(*, document_id: uuid.UUID) -> dict:
    document = proposal_service.get_document(document_id)
    if document.status != "GENERATED":
        raise proposal_service.ProposalError(f"Document {document.id} has no generated file ({document.status})")
    ttl = int(system_parameter_service.get_value(TTL_PARAMETER))
    expires = timezone.now() + datetime.timedelta(seconds=ttl)
    token = signing.dumps(
        {"d": str(document.id), "t": str(CurrentTenantProvider.require().value), "exp": int(expires.timestamp())},
        salt=_SALT,
        compress=True,
    )
    actor = CurrentActorProvider.get()
    _audit.record(
        action="document.signed_url_created",
        entity_type="Document",
        entity_id=str(document.id),
        metadata={"expiresAt": expires.isoformat(), "ttlSeconds": ttl, "actor": actor.actor_id if actor else None},
    )
    return {"url": f"/api/v1/documents/signed/{token}", "expiresAt": expires, "expiresInSeconds": ttl}


def open_link(token: str) -> tuple[bytes, str, str | None]:
    """Valida o token e devolve (ficheiro, content-type, nome)."""
    try:
        payload = signing.loads(token, salt=_SALT)
    except signing.BadSignature:
        raise InvalidDocumentLinkError("Ligação inválida.") from None
    if payload.get("exp", 0) < timezone.now().timestamp():
        raise InvalidDocumentLinkError("Ligação expirada. Peça uma nova.")
    # Contexto de leitura limitado ao inquilino do token (sem permissões).
    actor = Actor(
        actor_id="signed-link",
        tenant_id=TenantId.parse(payload["t"]),
        roles=frozenset(),
        scopes=frozenset({Scope.READ}),
        actor_type="SERVICE",
    )
    bound = CurrentActorProvider.bind(actor)
    try:
        document = proposal_service.get_document(uuid.UUID(payload["d"]))
        data = proposal_service.read_file(document)
        _audit.record(
            action="document.signed_url_opened",
            entity_type="Document",
            entity_id=str(document.id),
            metadata={"checksum": document.checksum},
        )
        return data, document.content_type or "application/octet-stream", document.file_name
    finally:
        CurrentActorProvider.reset(bound)
