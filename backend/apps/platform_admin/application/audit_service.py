from typing import Any
from apps.platform_admin.infrastructure.models import PlatformAuditEvent

_SENSITIVE = {"password","temporaryPassword","token","accessToken","refreshToken","secret","authorization"}
def _sanitize(v: Any):
    if isinstance(v, dict): return {k: _sanitize(x) for k,x in v.items() if k not in _SENSITIVE}
    if isinstance(v, list): return [_sanitize(x) for x in v]
    return v
def record_platform_audit(*, actor_id: str, action: str, entity_type: str, entity_id: str|None=None, correlation_id: str|None=None, metadata: dict|None=None):
    PlatformAuditEvent.objects.create(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, correlation_id=correlation_id, metadata_json=_sanitize(metadata or {}))
