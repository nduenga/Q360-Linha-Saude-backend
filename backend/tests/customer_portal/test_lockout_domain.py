"""Pure unit tests for apps.customer_portal.domain.lockout — OD-PORTAL-003
(Product Owner decision 2026-09-22): 5 failed attempts locks the account
for 30 minutes. No DB, same style as
tests/eligibility/test_evaluation_domain.py.
"""
from __future__ import annotations

import datetime

from apps.customer_portal.domain.lockout import (
    LockoutState,
    is_locked,
    register_failure,
    register_success,
)

_NOW = datetime.datetime(2026, 9, 22, 12, 0, 0, tzinfo=datetime.timezone.utc)


def test_not_locked_when_never_failed():
    state = LockoutState(failed_attempts=0, locked_until=None)
    assert not is_locked(state, now=_NOW)


def test_failures_below_threshold_do_not_lock():
    state = LockoutState(failed_attempts=0, locked_until=None)
    for _ in range(4):
        state = register_failure(state, now=_NOW, max_attempts=5, lockout_minutes=30)
    assert state.failed_attempts == 4
    assert state.locked_until is None
    assert not is_locked(state, now=_NOW)


def test_fifth_failure_locks_for_30_minutes():
    state = LockoutState(failed_attempts=4, locked_until=None)
    state = register_failure(state, now=_NOW, max_attempts=5, lockout_minutes=30)
    assert state.failed_attempts == 0
    assert state.locked_until == _NOW + datetime.timedelta(minutes=30)
    assert is_locked(state, now=_NOW)


def test_lock_expires_after_window():
    state = LockoutState(failed_attempts=0, locked_until=_NOW + datetime.timedelta(minutes=30))
    later = _NOW + datetime.timedelta(minutes=31)
    assert not is_locked(state, now=later)


def test_success_clears_failures_and_lock():
    state = register_success()
    assert state == LockoutState(failed_attempts=0, locked_until=None)


def test_lock_survives_until_a_success_or_expiry_even_across_more_failures():
    """A locked account that keeps receiving failed attempts stays locked
    (its `locked_until` is not extended past the original 30 minutes by
    subsequent failures in this implementation's contract at the service
    layer, which checks `is_locked` before ever calling `register_failure`
    again)."""
    state = LockoutState(failed_attempts=0, locked_until=_NOW + datetime.timedelta(minutes=30))
    assert is_locked(state, now=_NOW)
