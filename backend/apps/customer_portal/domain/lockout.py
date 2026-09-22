"""Pure lockout policy — OD-PORTAL-003 (ROADMAP_PORTAL_CLIENTE.md,
Product Owner decision 2026-09-22): 5 failed OTP attempts locks a
`CustomerAccount` for 30 minutes. No DB/Django import here — same
determinism discipline as `apps.eligibility.domain.evaluation`.
"""
from __future__ import annotations

import dataclasses
import datetime


@dataclasses.dataclass(frozen=True, slots=True)
class LockoutState:
    failed_attempts: int
    locked_until: datetime.datetime | None


def is_locked(state: LockoutState, *, now: datetime.datetime) -> bool:
    return state.locked_until is not None and state.locked_until > now


def register_failure(
    state: LockoutState, *, now: datetime.datetime, max_attempts: int, lockout_minutes: int
) -> LockoutState:
    """One more failed OTP/credential check. Reaching `max_attempts` locks
    the account and resets the counter (so the next lock also needs
    `max_attempts` fresh failures, rather than triggering on failure #1
    forever)."""
    failed_attempts = state.failed_attempts + 1
    if failed_attempts >= max_attempts:
        return LockoutState(
            failed_attempts=0, locked_until=now + datetime.timedelta(minutes=lockout_minutes)
        )
    return LockoutState(failed_attempts=failed_attempts, locked_until=state.locked_until)


def register_success() -> LockoutState:
    return LockoutState(failed_attempts=0, locked_until=None)
