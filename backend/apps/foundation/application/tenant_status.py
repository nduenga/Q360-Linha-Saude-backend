"""Estado do tenant visto pelos pedidos autenticados.

Um tenant SUSPENDED/INACTIVE deixa de poder usar a API de imediato (não só
no login): o resultado é guardado em cache 30 s por tenant e limpo quando a
plataforma altera o estado. Um tenant sem linha (ex.: testes com ids
sintéticos) não é bloqueado aqui; a ligação ao tenant é validada noutros
pontos."""
from __future__ import annotations

from django.core.cache import cache

_SECONDS = 30
_OK = "ACTIVE"


def _key(tenant_id) -> str:
    return f"tenant-status:{tenant_id}"


def invalidate(tenant_id) -> None:
    cache.delete(_key(tenant_id))


def is_blocked(tenant_id) -> bool:
    from apps.foundation.infrastructure.models import Tenant

    status = cache.get(_key(tenant_id))
    if status is None:
        try:
            status = Tenant.objects.filter(id=tenant_id).values_list("status", flat=True).first() or _OK
        except RuntimeError:  # contexto sem acesso à base de dados (testes unitários)
            return False
        cache.set(_key(tenant_id), status, _SECONDS)
    return status != _OK
