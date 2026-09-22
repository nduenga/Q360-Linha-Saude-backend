"""6-digit OTP generation/hashing (OD-PORTAL-001: email OTP only).

Reuses Django's own password hasher (`django.contrib.auth.hashers`) to
store `otp_hash` — the same real, audited primitive the framework uses
for credentials, not a bespoke digest. `django.contrib.auth` needs no
`User` model or its own tables for this; `make_password`/`check_password`
are plain functions.
"""
from __future__ import annotations

import secrets

from django.contrib.auth.hashers import check_password, make_password

_OTP_DIGITS = 6


def generate_otp() -> str:
    return f"{secrets.randbelow(10 ** _OTP_DIGITS):0{_OTP_DIGITS}d}"


def hash_otp(otp: str) -> str:
    return make_password(otp)


def verify_otp(otp: str, otp_hash: str) -> bool:
    return check_password(otp, otp_hash)
