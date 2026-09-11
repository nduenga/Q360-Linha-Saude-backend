"""Named use cases from DOC-004 s7 that protect a real invariant — everyday
CRUD lives in product_service.py / pricing_parameter_service.py instead."""
from __future__ import annotations

from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.domain.enums import VersionedConfigStatus
from apps.product.domain.errors import ImmutableVersionError
from apps.product.infrastructure.models import ProductVersion

_audit = AuditService(DjangoAuditRepositoryAdapter())


class PublishProductVersionUseCase:
    """DOC-004 s7: "Valida e publica versão imutável".

    `checksum` is left unset: ART-005 declares the column nullable and no
    approved document specifies what it must hash or how — computing one
    here would be inventing a business rule, not implementing one.
    """

    def execute(self, version: ProductVersion) -> ProductVersion:
        actor = CurrentActorProvider.get()
        # Conditional UPDATE (not read-then-save): the WHERE clause only
        # matches a still-DRAFT row, so two concurrent publish calls for
        # the same version can never both succeed — the second affects 0
        # rows and gets ImmutableVersionError, instead of a race where both
        # read DRAFT before either commits.
        updated = ProductVersion.objects.filter(
            id=version.id, status=VersionedConfigStatus.DRAFT.value
        ).update(
            status=VersionedConfigStatus.PUBLISHED.value,
            published_at=timezone.now(),
            published_by=actor.actor_id if actor else None,
        )
        if updated == 0:
            raise ImmutableVersionError(
                f"ProductVersion {version.id} is not DRAFT; only a DRAFT version can be published"
            )
        version.refresh_from_db()

        _audit.record(
            action="product_version.published",
            entity_type="ProductVersion",
            entity_id=str(version.id),
            metadata={"productId": str(version.product_id), "versionNo": version.version_no},
        )
        return version
