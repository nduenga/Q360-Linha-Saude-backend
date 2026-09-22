"""A stricter, dedicated rate limit for the 2 public pre-auth endpoints
(request-access, verify-otp) — ROADMAP_PORTAL_CLIENTE.md Fase 0: "são o
único ponto do sistema acessível sem já ter um token válido, logo o alvo
natural de força bruta". `apps.foundation.interfaces.middleware.
RateLimitMiddleware` already guards every endpoint by IP/tenant, but its
limit (`RATE_LIMIT_REQUESTS`, default 120/60s) is shared across all
traffic from that identity — far too loose for guessing
quoteNumber/registrationNumber pairs. Same fixed-window, in-process
pattern as that middleware, deliberately not merged into it (this guard
is keyed by tenant+IP+email, one extra dimension `RateLimitMiddleware`
has no reason to know about).
"""
from __future__ import annotations

import threading
import time

from django.conf import settings

_lock = threading.Lock()
_buckets: dict[tuple[str, int], int] = {}


def is_rate_limited(*, tenant_id: str, remote_addr: str, email: str) -> bool:
    limit = settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT
    if limit <= 0:
        return False
    window = max(1, settings.CUSTOMER_PORTAL_LOGIN_RATE_WINDOW_SECONDS)
    now = time.monotonic()
    bucket = int(now // window)
    key = (f"{tenant_id}:{remote_addr}:{email}", bucket)
    with _lock:
        global _buckets
        _buckets = {k: v for k, v in _buckets.items() if k[1] >= bucket - 1}
        count = _buckets.get(key, 0) + 1
        _buckets[key] = count
    return count > limit
