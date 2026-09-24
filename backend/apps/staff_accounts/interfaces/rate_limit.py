"""Rate limit for the one public pre-auth endpoint, `POST /api/v1/auth/login`
- same fixed-window, in-process pattern as
apps.customer_portal.interfaces.rate_limit (deliberately a separate small
module rather than a shared one - each is keyed by a different identity
tuple and reads its own settings, not worth a premature abstraction over).
"""
from __future__ import annotations

import threading
import time

from django.conf import settings

_lock = threading.Lock()
_buckets: dict[tuple[str, int], int] = {}


def is_login_rate_limited(*, remote_addr: str, email: str) -> bool:
    limit = settings.Q360_STAFF_LOGIN_RATE_LIMIT
    if limit <= 0:
        return False
    window = max(1, settings.Q360_STAFF_LOGIN_RATE_WINDOW_SECONDS)
    now = time.monotonic()
    bucket = int(now // window)
    key = (f"{remote_addr}:{email}", bucket)
    with _lock:
        global _buckets
        _buckets = {k: v for k, v in _buckets.items() if k[1] >= bucket - 1}
        count = _buckets.get(key, 0) + 1
        _buckets[key] = count
    return count > limit
