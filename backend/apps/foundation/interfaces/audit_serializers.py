"""AuditEvent serializer matching ART-006 `AuditEvent` schema verbatim.

Field names are camelCase exactly as documented in the OpenAPI contract;
`AuditEvent` does not expose `actorType`, `traceId`, `source` because they
are not part of the published wire shape (DOC-004 s2 precedence rule).
`metadata` is serialized directly from `metadata_json` (the DB column)
using the same `metadata` wire name the contract names it.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.foundation.infrastructure.models import AuditEvent
from apps.staff_accounts.infrastructure.models import StaffAccount

_FORBIDDEN_KEYS = {
    "token", "password", "secret", "authorization", "access_token",
    "refresh_token", "jwt", "api_key",
}


def _safe_metadata(value):
    if isinstance(value, dict):
        return {
            key: _safe_metadata(item)
            for key, item in value.items()
            if not isinstance(key, str) or key.lower() not in _FORBIDDEN_KEYS
        }
    if isinstance(value, list):
        return [_safe_metadata(item) for item in value]
    return value


class AuditEventSerializer(serializers.Serializer):
    id = serializers.UUIDField()

    actorId = serializers.CharField(
        source="actor_id",
        allow_null=True,
        default=None,
    )

    authorName = serializers.SerializerMethodField()

    action = serializers.CharField()

    entityType = serializers.CharField(
        source="entity_type"
    )

    entityId = serializers.CharField(
        source="entity_id",
        allow_null=True,
        default=None,
    )

    occurredAt = serializers.DateTimeField(
        source="occurred_at"
    )

    correlationId = serializers.CharField(
        source="correlation_id",
        allow_null=True,
        default=None,
    )

    metadata = serializers.SerializerMethodField()

    def get_authorName(self, obj):
        if not obj.actor_id:
            return None

        return (
            StaffAccount.objects
            .filter(
                id=obj.actor_id,
                tenant_id=obj.tenant_id,
            )
            .values_list("name", flat=True)
            .first()
        )

    def get_metadata(self, obj):
        return _safe_metadata(
            obj.metadata_json or {}
        )
        
        

