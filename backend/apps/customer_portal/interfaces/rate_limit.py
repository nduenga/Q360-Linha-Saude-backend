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
_ip_lock = threading.Lock()
_ip_buckets: dict[tuple[str, int], int] = {}


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


def is_ip_rate_limited(*, tenant_id: str, remote_addr: str) -> bool:
    """Compensating control for request-access now telling the caller
    exactly which of quoteNumber/registrationNumber is wrong (Product
    Owner decision, 2026-09-26 — see apps.customer_portal.domain.errors
    module docstring). Deliberately keyed WITHOUT `email`: `email` is
    never verified before this point (it is only where the OTP gets sent
    if the rest matches), so a caller can trivially defeat a per-email
    bucket by sending a different one on every request - this bucket
    can't be sidestepped that way. Separate in-process bucket from
    `is_rate_limited` above (deliberately not merged - different key
    shape, different limit)."""
    limit = settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP
    if limit <= 0:
        return False
    window = max(1, settings.CUSTOMER_PORTAL_LOGIN_RATE_WINDOW_SECONDS_PER_IP)
    now = time.monotonic()
    bucket = int(now // window)
    key = (f"{tenant_id}:{remote_addr}", bucket)
    with _ip_lock:
        global _ip_buckets
        _ip_buckets = {k: v for k, v in _ip_buckets.items() if k[1] >= bucket - 1}
        count = _ip_buckets.get(key, 0) + 1
        _ip_buckets[key] = count
    return count > limit
