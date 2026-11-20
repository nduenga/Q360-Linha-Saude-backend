from typing import Any
from apps.platform_admin.infrastructure.models import PlatformAuditEvent

_SENSITIVE = {"password","temporaryPassword","token","accessToken","refreshToken","secret","authorization"}
def _sanitize(v: Any):
    if isinstance(v, dict): return {k: _sanitize(x) for k,x in v.items() if k not in _SENSITIVE}
    if isinstance(v, list): return [_sanitize(x) for x in v]
    return v
def record_platform_audit(*, actor_id: str, action: str, entity_type: str, entity_id: str|None=None, correlation_id: str|None=None, metadata: dict|None=None, tenant_id=None):
    # Eventos sobre uma seguradora ficam com o tenant_id para filtrar e exportar por seguradora.
    if tenant_id is None and entity_type == "Tenant" and entity_id:
        tenant_id = entity_id
    PlatformAuditEvent.objects.create(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, correlation_id=correlation_id, metadata_json=_sanitize(metadata or {}), tenant_id=tenant_id)
